"""
PokerLeakLab API v2 — com persistência SQLite e autenticação JWT.
"""
from __future__ import annotations
import sys, os, re, uuid, time, json, logging, threading
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
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision
from leaklab.mtt_context import build_mtt_context
from leaklab.gto_utils import hand_to_type as _hand_to_type
from leaklab.preflop_gto_ranges import analyze_preflop as _analyze_preflop
from leaklab.session_metrics import build_session_metrics
from leaklab.leak_correlator import correlate_leaks
from leaklab.llm_explainer import explain_decisions, generate_tournament_summary, generate_tournament_narrative, generate_comparison_narrative, coach_chat_reply
from leaklab.report_generator import build_html_report, generate_pdf_bytes
from leaklab.email_digest import run_weekly_digest, verify_unsub_token, send_transactional_email

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
    get_coaches_with_payout_status, upsert_coach_payment, mark_coach_payment_paid,
    get_coach_finance_summary, get_coach_finance_students, get_coach_finance_history,
    get_admin_activity_logs,
    # Sprint D — BACK-016: WhatsApp
    get_user_by_phone, update_user_phone,
    # Sprint Q — FEAT-02 + FEAT-03: Daily Focus + XP Server-Side
    get_daily_focus, mark_daily_focus_done, reset_drill_sessions,
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
    validate_webhook, PLAN_AMOUNTS, STRIPE_WEBHOOK_SECRET,
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# ── Request instrumentation ───────────────────────────────────────────────────

@app.before_request
def _before():
    g.request_id = uuid.uuid4().hex[:8]
    g.t0 = time.monotonic()

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
    response.headers.setdefault('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    return response


@app.after_request
def _security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if os.environ.get('RENDER') or os.environ.get('LEAKLAB_PROD'):
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

# ── Auth ──────────────────────────────────────────────────────────────────────

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
    if len(password) < 8:
        return jsonify({'error': 'Senha deve ter pelo menos 8 caracteres'}), 400
    if get_user_by_email(email):
        return jsonify({'error': 'Email já cadastrado'}), 409
    if get_user_by_username(username):
        return jsonify({'error': 'Nome de usuário já está em uso'}), 409

    try:
        user_id = create_user(username, email, password, role)
        token   = generate_token(user_id, role)
        return jsonify({'token': token, 'user_id': user_id, 'role': role}), 201
    except Exception as e:
        log.exception("register error for %s", email)
        return jsonify({'error': 'Erro interno ao criar conta'}), 500


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


def _analyze_impl():
    quota_err = _check_upload_quota(g.user_id)
    if quota_err:
        return quota_err

    content = _extract_content(request)
    if not content:
        return jsonify({'error': 'Conteúdo ausente'}), 400

    try:
        hands = parse_pokerstars_file_from_text(content)
    except Exception as e:
        log.exception("parse error in /analyze")
        return jsonify({'error': 'Arquivo inválido ou formato não suportado'}), 422

    if not hands:
        return jsonify({'error': 'Nenhuma mão encontrada'}), 422

    results, hand_results, errors = _analyze_hands(hands)
    if not results:
        return jsonify({'error': 'Nenhuma decisão encontrada'}), 422

    metrics = build_session_metrics(results)
    leaks   = correlate_leaks(results)

    hero          = hands[0].hero or 'Hero'
    tournament_id = hands[0].tournament_id or ''
    site          = _detect_site(hands[0].raw_text if hasattr(hands[0],'raw_text') else '')
    played_at  = _extract_date(hands[0].raw_text if hasattr(hands[0],'raw_text') else '')
    raw_full   = '\n'.join(h.raw_text for h in hands if hasattr(h,'raw_text'))
    financials = _extract_financials(raw_full, hero)
    t_name     = _extract_tournament_name(raw_full, site, financials.get('buy_in'))

    # Bloquear duplicata
    existing = get_tournament(g.user_id, tournament_id)
    if existing:
        return jsonify({
            'error': f'Torneio {tournament_id} já foi importado anteriormente.',
            'duplicate': True,
            'tournament_id': tournament_id,
        }), 409

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
            n = reconcile_tournament_labels(tid)
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
        args=(results,),
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

    # Explicações LLM se solicitado
    if request.args.get('explain', '').lower() == 'true':
        all_decisions = [d for h in hand_results.values() for d in h['decisions']]
        explanations  = explain_decisions(all_decisions)
        from leaklab.llm_explainer import _key
        for hand in hand_results.values():
            for d in hand['decisions']:
                d['explanation'] = explanations.get(_key(d), '')

    import uuid
    return jsonify({
        'session_id':       str(uuid.uuid4()),
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
    })


@app.route('/analyze/tournament-summary', methods=['POST'])
@require_auth
@limiter.limit("20 per hour")
def tournament_summary():
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
    html = build_html_report(t, decisions, phases, hero)

    safe_id = tournament_id.replace(' ', '_')[:40]
    try:
        pdf_bytes = generate_pdf_bytes(html)
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="leaklab-report-{safe_id}.pdf"',
                'Cache-Control': 'no-store',
            }
        )
    except Exception:
        # WeasyPrint não disponível ou falhou (ex: libs GTK ausentes no Windows dev)
        return Response(
            html,
            mimetype='text/html',
            headers={
                'Content-Disposition': f'attachment; filename="leaklab-report-{safe_id}.html"',
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
        'evolution':    get_evolution_metrics(g.user_id, days, last_n=last_n),
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
    return jsonify(get_player_stats(g.user_id, days, last_n=last_n))


@app.route('/metrics/level', methods=['GET'])
@require_auth
def player_level():
    return jsonify(get_player_level(g.user_id))


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


@app.route('/player/spots/drill', methods=['GET'])
@require_auth
def player_drill_spots():
    """Sprint K — Retorna spots de mistakes para o Ghost Table Simulator."""
    limit  = min(int(request.args.get('limit', 10)), 20)
    street = request.args.get('street') or None
    spot   = request.args.get('spot')   or None
    spots  = get_drill_spots(g.user_id, limit=limit, street=street, spot=spot)
    stats  = get_drill_stats(g.user_id, days=30)
    return jsonify({'spots': spots, 'stats': stats})


def _resolve_best_action_from_node(row: dict) -> str:
    """Busca ação GTO ao vivo em gto_nodes (mesma lógica do /replay/<id>/gto).
    Fallback para decisions.gto_action → best_action se nenhum nó for encontrado."""
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

    _street_cards = {'flop': 3, 'turn': 4, 'river': 5}
    board_for_hash = board[:_street_cards.get(street, len(board))]

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
        return n

    node = None
    if hero_hand:
        node = _valid_node(get_gto_node(compute_spot_hash(street, position, board_for_hash, hero_hand, stack_bb, facing_bb)))
    if not node:
        node = _valid_node(get_gto_node(compute_spot_hash(street, position, board_for_hash, [], stack_bb, facing_bb)))
    if not node and facing_bb == 0:
        node = _valid_node(get_gto_node(compute_spot_hash(street, position, board_for_hash, [], stack_bb, 0.0)))
    # Fallback d (get_gto_node_by_spot) removido: usa algoritmo de hash diferente de compute_spot_hash,
    # podendo retornar nós completamente errados via colisão acidental.

    top_action = row.get('gto_action') or row.get('best_action') or 'fold'
    if node:
        if node.get('strategy_json'):
            try:
                strat = _j.loads(node['strategy_json'])
                top_action = max(strat, key=lambda k: strat[k].get('frequency', 0))
            except Exception:
                if node.get('gto_action'):
                    top_action = node['gto_action']
        elif node.get('gto_action'):
            top_action = node['gto_action']

    def _norm_action(raw: str) -> str:
        raw = (raw or '').lower()
        if raw in ('shove', 'jam', 'allin', 'all-in', 'all_in'):
            return 'jam'
        if raw.startswith('bet'):
            return 'bet'
        if raw.startswith('raise'):
            return 'bet' if facing_bb == 0 else 'raise'
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

    return a


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

    best_action = row['best_action']
    gto_action  = row.get('gto_action') or ''
    gto_label   = row.get('gto_label') or ''

    # Usa live GTO node lookup quando cobertura GTO disponível (mesmo pipeline do Replayer).
    # Evita erros por decisions.gto_action desatualizado ou hash match incorreto.
    if gto_action and gto_label not in ('wizard_pending', ''):
        best_action = _resolve_best_action_from_node(row)
    else:
        best_action = _norm_drill(best_action)
        # Guard: raise sem aposta anterior é semanticamente "bet"
        if float(row.get('facing_bet') or 0) == 0 and best_action == 'raise':
            best_action = 'bet'

    # Guard: BB pode check grátis — fold sem aposta é impossível.
    if float(row.get('facing_bet') or 0) == 0 and best_action == 'fold' and row.get('position') == 'BB':
        best_action = 'check'

    original_score = row['score']
    norm_new   = _norm_drill(new_action)
    is_correct = norm_new == best_action

    # Guard: quando facing_bet >= stack_bb, call e jam são mecanicamente equivalentes
    # (chamar o raise já coloca todas as fichas — shove não adiciona chips extras).
    facing_bet = float(row.get('facing_bet') or 0)
    stack_bb   = float(row.get('stack_bb') or 9999)
    if not is_correct and facing_bet > 0 and stack_bb > 0 and facing_bet >= stack_bb * 0.95:
        call_jam_set = {'call', 'jam'}
        if norm_new in call_jam_set and best_action in call_jam_set:
            is_correct = True
    new_score  = 0.02 if is_correct else original_score

    result = save_drill_session(
        user_id=g.user_id,
        decision_id=decision_id,
        new_action=new_action,
        new_score=new_score,
        original_score=original_score,
    )
    return jsonify({
        'is_correct':        is_correct,
        'best_action':       best_action,
        'new_action':        new_action,
        'new_score':         new_score,
        'original_score':    original_score,
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
    days = int(request.args.get('days', 90))
    lang = request.args.get('lang', 'pt-BR')
    return jsonify(get_leak_graph_data(g.user_id, days=days, lang=lang))


@app.route('/player/career', methods=['GET'])
@require_auth
def player_career():
    from leaklab.llm_explainer import generate_career_narrative
    lang       = request.args.get('lang', 'pt-BR')
    projection = get_career_projection(g.user_id)
    if not projection.get("insufficient_data"):
        projection["narrative"] = generate_career_narrative(projection, lang=lang)
    return jsonify(projection)


@app.route('/player/cognitive-failures', methods=['GET'])
@require_auth
def player_cognitive_failures():
    from leaklab.llm_explainer import generate_cognitive_narrative
    lang   = request.args.get('lang', 'pt-BR')
    days   = int(request.args.get('days', 90))
    report = get_cognitive_failure_report(g.user_id, days=days)
    if not report.get("insufficient_data") and report.get("patterns"):
        report["narrative"] = generate_cognitive_narrative(report["patterns"], lang=lang)
    return jsonify(report)


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


@app.route('/player/strategic-twin', methods=['GET'])
@require_auth
def player_strategic_twin():
    from leaklab.llm_explainer import generate_twin_narrative
    lang    = request.args.get('lang', 'pt-BR')
    days    = int(request.args.get('days', 180))
    profile = get_strategic_twin_profile(g.user_id, days=days)
    if not profile.get("insufficient_data") and profile.get("costly_spots"):
        profile["narrative"] = generate_twin_narrative(profile, lang=lang)
    return jsonify(profile)


@app.route('/player/daily-focus', methods=['GET'])
@require_auth
def player_daily_focus():
    return jsonify(get_daily_focus(g.user_id))


@app.route('/player/daily-focus/complete', methods=['POST'])
@require_auth
def player_daily_focus_complete():
    mark_daily_focus_done(g.user_id)
    return jsonify({'ok': True})


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
    return jsonify(get_player_level(student_id))


# ── AI Coach conversacional ──────────────────────────────────────────────────

@app.route('/coach/chat', methods=['POST'])
@require_auth
def coach_chat():
    data    = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Mensagem obrigatória'}), 400

    message = sanitize_llm_input(message, max_len=1000)

    from database.repositories import get_leak_ranking_gto_first
    days        = 90
    leak_data   = get_leak_ranking_gto_first(g.user_id, days)
    leaks       = leak_data['leaks']
    leak_source = leak_data['source']
    evolution   = get_evolution_metrics(g.user_id, days) or []
    freqs       = get_player_action_frequencies(g.user_id, days)
    hero        = g.user.get('username', 'Jogador')

    try:
        reply = coach_chat_reply(message, leaks, evolution, hero=hero,
                                  frequencies=freqs, leak_source=leak_source)
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

@app.route('/coach/students', methods=['GET'])
@require_coach
def coach_students():
    students = get_students(g.user_id)
    # Adicionar últimas métricas de cada aluno
    enriched = []
    for s in students:
        tournaments = get_tournaments(s['id'], limit=5)
        recent = tournaments[0] if tournaments else None
        enriched.append({
            **s,
            'recent_tournament': recent,
            'total_tournaments': len(tournaments),
        })
    return jsonify({'students': enriched})


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
    pot_sz  = row.get('pot_size')

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
    """
    shows_pat = re.compile(r'\b' + re.escape(hero) + r'\s*:\s*shows?\b')
    if not shows_pat.search(raw_text):
        return None
    won_pat = re.compile(r'\b' + re.escape(hero) + r'\s+collected\b')
    return 'won' if won_pat.search(raw_text) else 'lost'


def _analyze_hands(hands):
    results, hand_results, errors = [], {}, []
    for hand in hands:
        try:
            mtt    = build_mtt_context(hand)
            inputs = build_decision_inputs_for_hand(hand)
            hero   = hand.hero or 'Hero'
            sd_result = _detect_showdown(hand.raw_text or '', hero)
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
                }
                # Enriquecer decisões preflop com análise de range GTO
                if di['street'] == 'preflop':
                    try:
                        h_type = _hand_to_type(hand.hero_cards) if hand.hero_cards else None
                        if h_type:
                            _spot = di.get('spot', {})
                            _ctx  = di.get('context', {})
                            enriched['preflop_gto'] = _analyze_preflop(
                                position       = _spot.get('position', ''),
                                hero_hand_type = h_type,
                                stack_bb       = float(_spot.get('effectiveStackBb') or _ctx.get('heroStackBb') or 20),
                                action_taken   = di.get('player_action', ''),
                                facing_size    = float(_spot.get('facingSize') or 0),
                                vs_position    = _spot.get('villainPosition', ''),
                                is_3bet_pot    = bool(_spot.get('is3betPot') or di.get('is_3bet', False)),
                            )
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
    if 'PokerStars Hand #' in raw: return 'pokerstars'
    if 'Poker Hand #'      in raw: return 'ggpoker'
    if '888'               in raw: return '888poker'
    return 'unknown'


def _extract_tournament_name(raw: str, site: str, buy_in: float | None = None) -> str | None:
    """
    Extrai nome/descrição amigável do torneio para exibição na lista.
    GGPoker: captura nome explícito (ex: "Spin&Gold #14").
    PokerStars: detecta formato (SNG vs MTT) pelo número de jogadores únicos;
                SNGs têm exatamente N jogadores sem reposição, MTTs trazem novos
                jogadores de mesas quebradas (>9 únicos no arquivo completo).
    """
    import re
    if site == 'ggpoker':
        m = re.search(r'Tournament\s+#\d+,\s+(.+?)\s+Hold\'?em', raw, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    else:
        if buy_in is None or buy_in <= 0:
            return None
        # Contar jogadores únicos listados nos assentos para distinguir SNG de MTT
        seats = re.findall(r'^Seat \d+: (\S+) \(', raw, re.MULTILINE)
        unique_players = len(set(seats))
        fmt = 'SNG' if unique_players <= 9 else 'MTT'
        return f'{fmt} ${buy_in:.2f}'
    return None


def _extract_financials(raw: str, hero: str) -> dict:
    """
    Extrai buy-in e prêmio do hero do hand history.
    Suporta PokerStars e GGPoker.
    """
    import re
    result = {'buy_in': None, 'prize': None, 'profit': None, 'place': None}

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
            # PokerStars: hero busted without ITM — "hero finished the tournament" sem lugar/prêmio
            # Não usar o fallback de chips coletados (esses são potes normais do jogo, não prêmio)
            if re.search(re.escape(hero) + r'\s+finished the tournament', raw, re.IGNORECASE):
                result['prize'] = 0.0
            else:
                # GGPoker: soma chips coletados em potes como aproximação do prêmio
                collected = re.findall(
                    re.escape(hero) + r' collected (\d+(?:\.\d+)?) from', raw
                )
                if collected:
                    result['prize'] = sum(float(x) for x in collected)

    if result['buy_in'] and result['prize'] is not None:
        result['profit'] = round(result['prize'] - result['buy_in'], 2)

    return result


def _extract_date(raw: str) -> str | None:
    """
    Extrai a data do jogo do hand history.
    Suporta PokerStars (2025/07/22) e GGPoker (2026/04/24).
    """
    import re
    m = re.search(r'(\d{4})/(\d{2})/(\d{2})\s+\d{2}:\d{2}:\d{2}', raw)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    m = re.search(r'(\d{4})/(\d{2})/(\d{2})', raw)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    return None


# ── Error handlers ────────────────────────────────────────────────────────────


# ── Coach system endpoints ────────────────────────────────────────────────────

@app.route('/coach/invite-key', methods=['GET'])
@require_coach
def coach_invite_key():
    """Retorna (ou gera) a chave de convite do coach."""
    key = assign_invite_key(g.user_id)
    return jsonify({'invite_key': key})


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
    msgs = get_coach_messages(g.user_id, student_id, limit=100)
    mark_messages_read(g.user_id, student_id, reader_role='coach')
    return jsonify({'messages': msgs})


@app.route('/coach/student/<int:student_id>/messages', methods=['POST'])
@require_coach
def coach_messages_send(student_id: int):
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
    """Lista alunos com métricas recentes."""
    students = get_students(g.user_id)
    enriched = []
    for s in students:
        tournaments = get_tournaments(s['id'], limit=5)
        recent = tournaments[0] if tournaments else None
        # Calcular tendência (último vs anterior)
        trend = None
        if len(tournaments) >= 2:
            diff = (tournaments[0]['avg_score'] or 0) - (tournaments[1]['avg_score'] or 0)
            trend = 'improving' if diff < -0.005 else 'worsening' if diff > 0.005 else 'stable'
        enriched.append({
            **s,
            'recent_tournament': recent,
            'total_tournaments': len(tournaments),
            'trend': trend,
        })
    # Ordenar: alunos com piores scores primeiro (mais precisam de atenção)
    enriched.sort(
        key=lambda x: x['recent_tournament']['avg_score'] if x['recent_tournament'] else 0,
        reverse=True
    )
    return jsonify({'students': enriched})


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
    for d in decisions:
        d['note'] = _enrich_note(d)
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
                   d.action_taken, d.best_action, d.label, d.score,
                   d.position, d.icm_pressure, d.m_ratio, d.stack_bb,
                   t.tournament_id, t.site,
                   COALESCE(a.coach_override_label, d.label) AS effective_label
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            LEFT JOIN coach_hand_annotations a
                   ON a.decision_id = d.id AND a.student_id = t.user_id
            WHERE t.user_id = ?
              AND COALESCE(a.coach_override_label, d.label) IN ('clear_mistake', 'small_mistake')
            ORDER BY d.score DESC
            LIMIT ?
        """, (student_id, limit)).fetchall()
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
        plan = generate_study_plan(leaks, evolution, icm, hero=hero, user_id=student_id,
                                   force_new=force_new, player_stats=player_stats,
                                   leak_source=leak_source)
        return jsonify(plan)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


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
    _db_all_c  = get_decisions(t['id'])
    _db_hand_c = [d for d in _db_all_c if str(d.get('hand_id')) == str(hand_id)]
    _gto_idx_c = {
        (d.get('street',''), (d.get('action_taken','') or '').rstrip('s') or d.get('action_taken','')):
        {'gto_label': d.get('gto_label'), 'gto_action': d.get('gto_action')}
        for d in _db_hand_c if d.get('gto_label')
    }
    try:
        from leaklab.pipeline import build_decision_inputs_for_hand
        from leaklab.decision_engine_v11 import evaluate_decision as _eval
        live_decisions = []
        for di in build_decision_inputs_for_hand(target):
            r = _eval(di)
            action_norm = (r.get('actionTaken','') or '').rstrip('s') or r.get('actionTaken','')
            gto_data = _gto_idx_c.get((di['street'], action_norm), {})
            live_decisions.append({
                'hand_id': str(target.hand_id), 'street': di['street'],
                'action_taken': r.get('actionTaken', ''), 'best_action': r.get('bestAction', ''),
                'label': r['evaluation']['label'], 'score': r['evaluation']['mistakeScore'],
                'context': di.get('context', {}), 'math': di.get('math', {}),
                'breakdown': r['evaluation'].get('scoreBreakdown', {}),
                'gto_label':  gto_data.get('gto_label'),
                'gto_action': gto_data.get('gto_action'),
            })
        hand_decisions = live_decisions
    except Exception:
        hand_decisions = _db_hand_c
    replay = _build_replay_data(target, hand_decisions, t.get('hero', target.hero))
    # Attach coach annotations for decisions in this hand
    db_decisions = _db_all_c
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

    cache_key = f"decision:{decision_id}"
    cached = get_llm_cache(g.user_id, cache_key)
    if cached and not data.get('force_new'):
        return jsonify({'analysis': cached, 'cached': True})

    ai_err = _check_ai_quota(g.user_id)
    if ai_err:
        return ai_err

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

        plan = generate_study_plan(leaks, evolution, icm, hero=hero, user_id=g.user_id,
                                   force_new=force_new, player_stats=player_stats,
                                   leak_source=leak_source)

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
        conn.execute("DELETE FROM decisions WHERE tournament_id=?", (db_id,))
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

    # Buscar decisões do banco para enriquecer com gto_label/gto_action
    _db_all      = get_decisions(t['id'])
    _db_hand     = [d for d in _db_all if str(d.get('hand_id')) == str(hand_id)]
    # Índice (street, action_taken) → dados GTO do banco
    _gto_index   = {
        (d.get('street',''), (d.get('action_taken','') or '').rstrip('s') or d.get('action_taken','')):
        {'gto_label': d.get('gto_label'), 'gto_action': d.get('gto_action'),
         'facing_bet': d.get('facing_bet')}
        for d in _db_hand if d.get('gto_label')
    }

    # Re-executar o engine ao vivo para garantir scores/labels atualizados
    # O banco pode ter dados de versões antigas do engine com bugs corrigidos
    try:
        from leaklab.pipeline import build_decision_inputs_for_hand
        from leaklab.decision_engine_v11 import evaluate_decision as _eval
        live_decisions = []
        for di in build_decision_inputs_for_hand(target):
            r = _eval(di)
            action_norm = (r.get('actionTaken','') or '').rstrip('s') or r.get('actionTaken','')
            gto_data = _gto_index.get((di['street'], action_norm), {})
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
                'gto_label':    gto_data.get('gto_label'),
                'gto_action':   gto_data.get('gto_action'),
                'facing_bet':   gto_data.get('facing_bet'),
                '_di':          di,
            })
        hand_decisions = live_decisions
    except Exception:
        # Fallback para dados do banco se engine falhar
        hand_decisions = _db_hand

    # Construir replay data (parte pesada — vai pro cache)
    replay = _build_replay_data(target, hand_decisions, t.get('hero', target.hero))
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


def _build_replay_data(hand, decisions_db, hero_override=None):
    """Constrói a timeline completa de replay a partir de uma ParsedHand."""
    import re as _re
    from leaklab.hand_state_builder import _normalize_action

    def _parse_summary(raw):
        """Extrai resultado, vencedores e cartas reveladas do SUMMARY."""
        start = raw.find('*** SUMMARY ***')
        if start < 0: return {}
        s = raw[start:]
        result = {'winners':[], 'seats':[], 'board':[], 'total_pot':None}
        m = _re.search(r'Total pot (\d+)', s)
        if m: result['total_pot'] = int(m.group(1))
        m = _re.search(r'Board \[([^\]]+)\]', s)
        if m: result['board'] = m.group(1).split()
        for line in s.split('\n'):
            m = _re.match(r'Seat (\d+): (.+?) (?:\(.*?\) )?showed \[([^\]]+)\] and won \((\d+)\) with (.+)', line)
            if m:
                result['seats'].append({'seat':int(m.group(1)),'player':m.group(2).strip(),
                    'cards':m.group(3).split(),'won':int(m.group(4)),
                    'hand_desc':m.group(5).strip(),'outcome':'won'}); continue
            m = _re.match(r'Seat (\d+): (.+?) (?:\(.*?\) )?mucked \[([^\]]+)\]', line)
            if m:
                result['seats'].append({'seat':int(m.group(1)),'player':m.group(2).strip(),
                    'cards':m.group(3).split(),'won':0,
                    'hand_desc':'mucked','outcome':'lost'}); continue
            m = _re.match(r'Seat (\d+): (.+?) (?:\(.*?\) )?collected \((\d+)\)', line)
            if m:
                result['seats'].append({'seat':int(m.group(1)),'player':m.group(2).strip(),
                    'cards':[],'won':int(m.group(3)),
                    'hand_desc':'collected','outcome':'won'})
        result['winners'] = [s for s in result['seats'] if s['outcome']=='won']
        return result

    hero = hero_override or hand.hero

    # Extrair seats, stacks e bounties do raw_text
    seats = {}
    _bounties = getattr(hand, 'bounties', {}) or {}
    for line in hand.raw_text.split('\n'):
        m = _re.match(r'Seat (\d+): (.+?) \((\d+) in chips\)', line)
        if m:
            player = m.group(2).strip()
            seat_d = {'player': player, 'stack': int(m.group(3))}
            if player in _bounties:
                seat_d['bounty'] = _bounties[player]
            seats[int(m.group(1))] = seat_d
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
    pos_names = ['BTN','SB','BB','UTG','UTG+1','UTG+2','MP','HJ','CO']
    positions = {
        s: pos_names[(i - btn_idx) % n] if (i - btn_idx) % n < len(pos_names) else f'P{(i-btn_idx)%n}'
        for i, s in enumerate(seat_nums)
    }

    # Mapear erros por (street, action_taken) — inclui dados matemáticos do engine
    # Normalizar: banco usa 'fold','call','raise'; parser usa 'folds','calls','raises'
    def _norm(a):
        if not a:
            return ''
        a = a.rstrip('s') if a.endswith('s') else a
        return 'allin' if a in ('all-in', 'allin', 'jam', 'shove') else a

    # Mapa unificado: todas as decisões do hero, indexadas por (street, action)
    all_decisions = {}
    for d in decisions_db:
        key = (d.get('street', ''), _norm(d.get('action_taken', '')))
        all_decisions[key] = d

    # Re-rodar o engine para enriquecer TODAS as decisões hero com dados matemáticos
    # e análise de range preflop GTO
    try:
        from leaklab.pipeline import build_decision_inputs_for_hand
        from leaklab.decision_engine_v11 import evaluate_decision
        from leaklab.gto_utils import hand_to_type
        from leaklab.preflop_gto_ranges import analyze_preflop
        engine_inputs = build_decision_inputs_for_hand(hand)
        for di in engine_inputs:
            r   = evaluate_decision(di)
            key = (di['street'], _norm(r.get('actionTaken', '')))
            if key in all_decisions:
                all_decisions[key]['context']   = di.get('context', {})
                all_decisions[key]['math']      = di.get('math', {})
                all_decisions[key]['breakdown'] = r['evaluation'].get('scoreBreakdown', {})
                all_decisions[key]['_di']       = di  # spot params for GTO strategy lookup
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
                            _pf_is_3bet_pot = (_pf_n_raises_before >= 2
                                              or bool(spot.get('is3betPot'))
                                              or bool(di.get('is_3bet', False)))
                            _pf_result = analyze_preflop(
                                position       = _pf_pos,
                                hero_hand_type = h_type,
                                stack_bb       = _pf_stack_bb,
                                action_taken   = di.get('player_action', ''),
                                facing_size    = _pf_facing_bb,
                                vs_position    = spot.get('villainPosition', ''),
                                is_3bet_pot    = _pf_is_3bet_pot,
                                n_players      = spot.get('nPlayers'),
                            )
                            # Fallback for call-vs-shove (no vs_3bet data yet):
                            # use RFI range membership as proxy for shove-call quality
                            if (not _pf_result.get('available')
                                    and di.get('player_action', '') in ('call', 'allin')
                                    and _pf_facing_bb >= _pf_stack_bb * 0.40):
                                _rfi_check = analyze_preflop(
                                    position=_pf_pos, hero_hand_type=h_type,
                                    stack_bb=_pf_stack_bb, action_taken='raise',
                                    facing_size=0.0, vs_position='',
                                )
                                if _rfi_check.get('available'):
                                    _rq = _rfi_check.get('action_quality', 'unknown')
                                    _q  = 'correct' if _rq == 'correct' else ('acceptable' if _rq == 'acceptable' else 'leak')
                                    _pf_result = {
                                        'available': True,
                                        'recommended_actions': ['call' if _q != 'leak' else 'fold'],
                                        'action_quality': _q,
                                        'in_range': _rfi_check.get('in_range', False),
                                        'scenario': 'vs_shove_fallback',
                                        # Campos completos para frontend renderizar
                                        'hand_type': h_type,
                                        'stack_bucket': _rfi_check.get('stack_bucket', f'{int(_pf_stack_bb)}bb'),
                                        'stack_bb': _pf_stack_bb,
                                        'position': _pf_pos,
                                        'vs_position': '',
                                        'range_pct': _rfi_check.get('range_pct', 0),
                                        'range_hands': _rfi_check.get('range_hands', ''),
                                        'action_taken': 'call',
                                        'pro_notes': _rfi_check.get('pro_notes', []),
                                        'reasoning': (
                                            'Mão premium em range de abertura — call de shove correto.'
                                            if _q == 'correct' else
                                            'Mão no limite do range — call de shove aceitável.'
                                            if _q == 'acceptable' else
                                            'Mão fora do range de abertura — fold vs shove recomendado.'
                                        ),
                                    }
                            all_decisions[key]['preflop_gto'] = _pf_result
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
    UNCALLED_RE = _re.compile(r'Uncalled bet \((\d+)\) returned to (.+)')
    uncalled_returns = []
    for line in (hand.raw_text or '').split('\n'):
        _mu = UNCALLED_RE.match(line.strip())
        if _mu:
            uncalled_returns.append({'amount': int(_mu.group(1)), 'player': _mu.group(2).strip()})

    current_revealed = {}  # seat_str -> [cards], accumulates as shows happen

    # Extrair antes e blinds do raw_text (parser não os captura em hand.actions)
    antes   = []
    blinds  = []
    for line in hand.raw_text.split('\n'):
        m_ante  = _re.match(r'(.+): posts the ante (\d+)', line)
        m_blind = _re.match(r'(.+): posts (small|big) blind (\d+)', line)
        if m_ante:
            antes.append({'player': m_ante.group(1).strip(), 'amount': int(m_ante.group(2))})
        elif m_blind:
            blinds.append({'player': m_blind.group(1).strip(),
                           'type':   m_blind.group(2),
                           'amount': int(m_blind.group(3))})

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
                           'stack_bb': round(stacks[s] / bb, 1), 'pos': positions[s]}
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

        if action.action in ('calls', 'bets', 'raises', 'all-in') and amt:
            # Para raises: "raises X to Y" — X é o incremento, Y é o total colocado
            # O total que entra no pot é Y (não X), menos o que o jogador já tinha apostado
            # Para all-in: parser converte "bets/raises ... and is all-in" para 'all-in';
            #   se veio de raise ("raises X to Y"), extrair Y do raw; se de bet, amt é o total.
            if action.action == 'raises':
                m_to = _re.search(r'raises \d+ to (\d+)', action.raw or '')
                total_placed = int(m_to.group(1)) if m_to else amt
                already_in   = bets_r.get(pseat, 0)
                real_addition = total_placed - already_in
                pot += real_addition
                if pseat:
                    stacks[pseat]  = max(0, stacks[pseat] - real_addition)
                    bets_r[pseat]  = total_placed
            elif action.action == 'all-in':
                m_to = _re.search(r'raises \d+ to (\d+)', action.raw or '')
                if m_to:
                    # raise all-in: "raises X to Y and is all-in" — Y é o total colocado
                    total_placed  = int(m_to.group(1))
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

        err_key  = (action.street, _norm(action.action))
        decision = all_decisions.get(err_key) if action.player == hero else None

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
                'draw_profile':    math.get('drawProfile', 'none'),
                'm_ratio':         ctx.get('mRatio'),
                'icm_pressure':    ctx.get('icmPressure'),
                'hero_stack_bb':   ctx.get('heroStackBb') or float((decision.get('_di') or {}).get('spot', {}).get('effectiveStackBb') or 0) or None,
                'math_penalty':    bd.get('mathPenalty', 0),
                'range_penalty':   bd.get('rangePenalty', 0),
                'context_penalty': bd.get('contextPenalty', 0),
            }

        # GTO reconciliation — solver é fonte autoritativa quando disponível
        gto_label   = decision.get('gto_label')  if decision else None
        gto_action  = decision.get('gto_action') if decision else None
        engine_best = decision.get('best_action') if decision else None

        # Detectar incompatibilidade de spot GTO:
        # "check" não é ação válida quando o hero enfrenta uma aposta (engine diz "call")
        # "call" não é ação válida quando não há aposta (engine diz "check"/"bet")
        _FACING_BET  = {'call', 'calls'}
        _NO_BET      = {'check', 'checks', 'bet', 'bets'}
        gto_spot_mismatch = False
        if gto_action and engine_best:
            gto_n = _norm(gto_action)
            eng_n = _norm(engine_best)
            if eng_n in _FACING_BET and gto_n in _NO_BET:
                gto_spot_mismatch = True   # GTO diz check/bet mas hero enfrenta aposta
            elif eng_n in _NO_BET and gto_n in _FACING_BET:
                gto_spot_mismatch = True   # GTO diz call mas hero não enfrenta aposta

        # Calcular best_action e is_error reconciliados
        if gto_spot_mismatch:
            # Spot incompatível: ignora recomendação de ação do GTO, usa apenas o engine
            is_error        = (decision is not None and
                               decision.get('label', 'standard') in ('clear_mistake', 'small_mistake', 'marginal'))
            reconciled_best = engine_best
        elif gto_label in ('gto_correct', 'gto_mixed'):
            # GTO confirma ação jogada como válida — engine pode ter dado alarme falso
            is_error        = False
            reconciled_best = _norm(action.action)
        elif gto_label in ('gto_minor_deviation', 'gto_critical') and gto_action:
            # GTO aponta desvio — usa sua recomendação como "ideal"
            is_error        = True
            reconciled_best = gto_action
        else:
            # Sem dados GTO — confia apenas no engine
            is_error = (decision is not None and
                        decision.get('label', 'standard') in ('clear_mistake', 'small_mistake', 'marginal'))
            reconciled_best = engine_best

        # Detectar conflito engine vs GTO (quando não há mismatch de spot)
        gto_engine_conflict = (
            not gto_spot_mismatch
            and gto_label is not None
            and engine_best is not None
            and _norm(engine_best) != _norm(reconciled_best or '')
        )

        # Fetch full GTO strategy for display (all actions with freq + combos)
        gto_strategy = None
        if decision and gto_label and not gto_spot_mismatch:
            try:
                from leaklab.gto_solver import lookup_gto as _lookup_gto
                _di   = decision.get('_di', {})
                _spot = _di.get('spot', {})
                _ctx  = _di.get('context', {})
                _gto_result = _lookup_gto(
                    street         = action.street,
                    position       = _spot.get('position', _ctx.get('position', '')),
                    board          = _spot.get('board', []),
                    hero_hand      = _di.get('hero_cards', []),
                    hero_stack_bb  = float(_spot.get('effectiveStackBb', _ctx.get('heroStackBb', 20.0)) or 20.0),
                    action_seq     = _ctx.get('actionSeq', 'rfi'),
                    vs_position    = _spot.get('villainPosition', _ctx.get('vsPosition', '')),
                    facing_size_bb = float(decision.get('facing_bet', 0) or 0),
                    pot_bb         = float(_spot.get('potSize', 0) or 0),
                )
                if _gto_result.get('found') and _gto_result.get('strategy'):
                    gto_strategy = _gto_result['strategy']
            except Exception:
                pass

        # Re-evaluate is_error/reconciled_best using LIVE strategy (overrides stored gto_label)
        # Stored label may come from a mismatched or stale node; live frequency is ground truth.
        live_top_act = None
        if gto_strategy and not gto_spot_mismatch:
            acted_norm   = _norm(action.action)
            live_freq    = 0.0
            live_top_freq = 0.0
            for _gs in gto_strategy:
                _gs_act  = _norm(_gs.get('action', ''))
                _gs_freq = float(_gs.get('frequency') or 0)
                if (_gs_act == acted_norm
                        or acted_norm.startswith(_gs_act)
                        or _gs_act.startswith(acted_norm)):
                    live_freq = _gs_freq
                if _gs_freq > live_top_freq:
                    live_top_freq = _gs_freq
                    live_top_act  = _gs.get('action')
            if live_top_act:
                if live_freq >= 0.30:
                    is_error        = False
                    reconciled_best = acted_norm
                else:
                    is_error        = True
                    reconciled_best = live_top_act
                # Persiste o veredicto do solver — ele tem prioridade sobre RegLife.
                # Preflop usa analyze_preflop (ranges estáticos), nunca gto_nodes agregados.
                # O bloco preflop_override abaixo persiste os valores corretos para preflop.
                if action.street != 'preflop':
                    try:
                        from database.repositories import update_decision_gto as _upd_gto
                        # Thresholds alinhados com effectiveGtoLabel do frontend
                        _live_gto_label = (
                            'gto_correct'         if live_freq >= 0.60 else
                            'gto_mixed'           if live_freq >= 0.30 else
                            'gto_minor_deviation' if live_freq >= 0.10 else
                            'gto_critical'
                        )
                        _dec_id = next(
                            (d.get('id') for d in _db_hand
                             if _norm(d.get('street','')) == _norm(action.street)
                             and _norm(d.get('action_taken','')) == acted_norm),
                            None,
                        )
                        if _dec_id:
                            _upd_gto(_dec_id, _live_gto_label, live_top_act)
                    except Exception:
                        pass

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
                    from leaklab.preflop_gto_ranges import analyze_preflop as _apf
                    from leaklab.gto_utils import hand_to_type as _h2t
                    _ht = _h2t(_hc)
                    if _ht:
                        _pf = _apf(
                            position       = _pos,
                            hero_hand_type = _ht,
                            stack_bb       = _sb,
                            action_taken   = _norm(action.action),
                            facing_size    = _facing,
                            vs_position    = (_spot.get('villainPosition') or _spot.get('vsPosition', '')),
                        )
                        # Fallback for call-vs-shove: no specific vs_3bet data in ranges yet.
                        # When facing >= 40% of stack with call, use RFI range membership
                        # as proxy: in-range hand calling a shove = correct (KK, AA, AKs, QQ+).
                        # Out-of-range hand calling = leak. Pending: add vs_3bet range data.
                        if not _pf.get('available') and _norm(action.action) == 'call' and _facing >= _sb * 0.40:
                            _pf_rfi = _apf(position=_pos, hero_hand_type=_ht, stack_bb=_sb,
                                           action_taken='raise', facing_size=0.0, vs_position='')
                            if _pf_rfi.get('available'):
                                _rfi_quality = _pf_rfi.get('action_quality', 'unknown')
                                # Base com campos completos para o frontend renderizar
                                # corretamente (sem isto, hand_type/stack_bucket/range_pct
                                # ficam vazios e o card aparece sem informação)
                                _pf_base = {
                                    'available': True,
                                    'scenario': 'vs_shove_fallback',
                                    'hand_type': _ht,
                                    'stack_bucket': _pf_rfi.get('stack_bucket', f'{int(_sb)}bb'),
                                    'stack_bb': _sb,
                                    'position': _pos,
                                    'vs_position': '',
                                    'range_pct': _pf_rfi.get('range_pct', 0),
                                    'range_hands': _pf_rfi.get('range_hands', ''),
                                    'action_taken': _norm(action.action),
                                    'pro_notes': _pf_rfi.get('pro_notes', []),
                                }
                                if _rfi_quality == 'correct':
                                    _pf = {**_pf_base, 'recommended_actions': ['call'],
                                           'action_quality': 'correct', 'in_range': True}
                                elif _rfi_quality == 'acceptable':
                                    _pf = {**_pf_base, 'recommended_actions': ['call'],
                                           'action_quality': 'acceptable', 'in_range': True}
                                else:
                                    _pf = {**_pf_base, 'recommended_actions': ['fold'],
                                           'action_quality': 'leak', 'in_range': False}

                        if _pf.get('available') and _pf.get('recommended_actions'):
                            preflop_override_action = _pf['recommended_actions'][0]
                            _pf_quality = _pf.get('action_quality', 'unknown')
                            if _pf_quality in ('correct', 'acceptable'):
                                is_error        = False
                                reconciled_best = _norm(action.action)
                                gto_label       = 'gto_correct' if _pf_quality == 'correct' else 'gto_mixed'
                            elif _pf_quality in ('leak', 'major_leak'):
                                is_error        = True
                                reconciled_best = preflop_override_action
                                gto_label       = 'gto_critical'
                            # Persiste os valores corretos de preflop no banco.
                            # Sobrescreve qualquer lixo que gto_nodes agregados possam ter gravado.
                            try:
                                from database.repositories import update_decision_gto as _upd_gto_pf
                                _pf_acted_norm = _norm(action.action)
                                _pf_dec_id = next(
                                    (d.get('id') for d in _db_hand
                                     if _norm(d.get('street', '')) == 'preflop'
                                     and _norm(d.get('action_taken', '')) == _pf_acted_norm),
                                    None,
                                )
                                if _pf_dec_id:
                                    _upd_gto_pf(_pf_dec_id, gto_label, preflop_override_action)
                            except Exception:
                                pass
                except Exception:
                    pass

        timeline.append(snap({
            'type':               'action',
            'player':             action.player,
            'seat':               pseat,
            'action':             _normalize_action(action.action),
            'amount':             amt,
            'is_hero':            action.player == hero,
            'is_error':           is_error,
            'error_label':        decision.get('label')                             if decision else None,
            'error_score':        round(float(decision.get('score', 0)), 3)         if decision else None,
            'best_action':        reconciled_best                                    if decision else None,
            'engine_best':        engine_best if (gto_engine_conflict or gto_spot_mismatch) else None,
            'gto_label':          gto_label,
            'gto_action':         preflop_override_action or live_top_act or gto_action,
            'gto_strategy':       gto_strategy,
            'gto_spot_mismatch':  gto_spot_mismatch if gto_label else None,
            'preflop_gto':        decision.get('preflop_gto') if decision else None,
            'desc':           f"{action.player}: {_normalize_action(action.action)}"
                                + (f' {int(amt)}' if amt else ''),
            'revealed_cards': dict(current_revealed) if current_revealed else None,
            **tech,
        }))

    # Apply uncalled bet returns — correct pot/stacks/bets before showdown
    for ur in uncalled_returns:
        ur_player = ur['player']
        ur_amount = ur['amount']
        ur_pseat  = next((s for s, d in seats.items() if d['player'] == ur_player), None)
        pot                    = max(0, pot - ur_amount)
        if ur_pseat is not None:
            stacks[ur_pseat]   = stacks[ur_pseat] + ur_amount
            bets_r[ur_pseat]   = max(0, bets_r.get(ur_pseat, 0) - ur_amount)
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
                'name':        'Free',
                'price':       0,
                'currency':    'BRL',
                'tournaments': PLAN_LIMITS['free']['tournaments'],
                'ai_calls':    PLAN_LIMITS['free']['ai_calls'],
                'features':    [
                    f"{PLAN_LIMITS['free']['tournaments']} torneios/mês",
                    f"{PLAN_LIMITS['free']['ai_calls']} análises LeakLabs/mês",
                    'Detecção de leaks e score de decisão',
                    'Sistema de nível (7 níveis)',
                ],
            },
            {
                'id':          'starter',
                'name':        'Starter',
                'price':       1900,
                'currency':    'BRL',
                'tournaments': PLAN_LIMITS['starter']['tournaments'],
                'ai_calls':    PLAN_LIMITS['starter']['ai_calls'],
                'features':    [
                    f"{PLAN_LIMITS['starter']['tournaments']} torneios/mês",
                    f"{PLAN_LIMITS['starter']['ai_calls']} análises LeakLabs/mês",
                    'Plano de estudos personalizado',
                    'Histórico completo + evolução',
                    'Replayer com análise de decisão',
                ],
            },
            {
                'id':          'pro',
                'name':        'Pro',
                'price':       3900,
                'currency':    'BRL',
                'tournaments': PLAN_LIMITS['pro']['tournaments'],
                'ai_calls':    PLAN_LIMITS['pro']['ai_calls'],
                'features':    [
                    'Torneios ilimitados',
                    f"{PLAN_LIMITS['pro']['ai_calls']} análises LeakLabs/mês",
                    'Plano de estudos personalizado',
                    'Histórico completo + evolução',
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
@require_auth
def subscription_upgrade():
    """Upgrade manual (admin/debug). Produção usa /subscription/checkout."""
    data = request.get_json(silent=True) or {}
    new_plan = data.get('plan', 'pro')
    if new_plan not in PLAN_LIMITS:
        return jsonify({'error': 'Plano inválido'}), 400
    update_user_plan(g.user_id, new_plan)
    return jsonify({'ok': True, 'plan': new_plan})


# ── BACK-015: Stripe Billing ──────────────────────────────────────────────────

@app.route('/subscription/checkout', methods=['POST'])
@require_auth
@limiter.limit("10 per hour")
def subscription_checkout():
    """Cria assinatura Stripe incompleta e retorna client_secret para o frontend."""
    data = request.get_json(silent=True) or {}
    plan = data.get('plan')
    if plan not in ('starter', 'pro'):
        return jsonify({'error': 'Plano inválido. Use starter ou pro.'}), 400

    try:
        result = create_subscription(
            plan_name=plan,
            payer_email=g.user.get('email', ''),
            user_id=g.user_id,
        )
    except Exception as e:
        log.exception("Stripe checkout error for user %s plan %s", g.user_id, plan)
        if app.debug:
            return jsonify({'error': f'[DEBUG] Stripe: {e}'}), 502
        return jsonify({'error': 'Erro ao iniciar pagamento. Tente novamente.'}), 502

    return jsonify({
        'client_secret':   result['client_secret'],
        'subscription_id': result['subscription_id'],
    })


@app.route('/subscription/activate', methods=['POST'])
@require_auth
def subscription_activate():
    """Verifica PaymentIntent e ativa o plano — chamado após confirmPayment no frontend."""
    data              = request.get_json(silent=True) or {}
    plan              = data.get('plan')
    payment_intent_id = data.get('payment_intent_id')
    subscription_id   = data.get('subscription_id')

    if plan not in ('starter', 'pro'):
        return jsonify({'error': 'Plano inválido'}), 400
    if not payment_intent_id or not subscription_id:
        return jsonify({'error': 'payment_intent_id e subscription_id obrigatórios'}), 400

    pi = get_payment(payment_intent_id)
    if not pi or pi.get('status') not in ('succeeded', 'processing'):
        status = pi.get('status') if pi else 'not_found'
        return jsonify({'error': f'Pagamento não confirmado (status: {status})'}), 400

    update_user_plan(g.user_id, plan, subscription_id)
    save_payment(
        user_id=g.user_id,
        plan=plan,
        amount_cents=int(PLAN_AMOUNTS[plan] * 100),
        status='approved',
        gateway_id=payment_intent_id,
        gateway_sub_id=subscription_id,
    )
    return jsonify({'ok': True, 'plan': plan, 'subscription_id': subscription_id})


@app.route('/subscription/webhook', methods=['POST'])
def subscription_webhook():
    """Recebe eventos Stripe e atualiza planos/pagamentos."""
    import json as _json
    payload    = request.get_data()
    sig_header = request.headers.get('stripe-signature', '')

    if not STRIPE_WEBHOOK_SECRET:
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

    event_type = event.get('type', '') if isinstance(event, dict) else event.type
    obj        = (event.get('data', {}).get('object', {})
                  if isinstance(event, dict) else event.data.object)
    log.info("Stripe webhook type=%s", event_type)

    if event_type == 'payment_intent.succeeded':
        # PaymentIntent concluído — ativa plano via metadata
        meta      = obj.get('metadata', {}) if isinstance(obj, dict) else obj.metadata
        user_id   = int(meta.get('user_id', 0))
        plan_name = meta.get('plan_name', '')
        pi_id     = obj.get('id', '') if isinstance(obj, dict) else obj.id
        amount    = obj.get('amount', 0) if isinstance(obj, dict) else obj.amount
        if user_id and plan_name:
            update_user_plan(user_id, plan_name, str(pi_id))
            save_payment(
                user_id=user_id, plan=plan_name,
                amount_cents=int(amount),
                status='approved',
                gateway_id=str(pi_id),
                gateway_sub_id=str(pi_id),
            )

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
    """Cancela a assinatura ativa do usuário."""
    sub_id = g.user.get('mp_subscription_id')
    if not sub_id:
        return jsonify({'error': 'Nenhuma assinatura ativa encontrada'}), 400
    if cancel_subscription(sub_id):
        update_user_plan(g.user_id, 'free', None)
        return jsonify({'ok': True, 'plan': 'free'})
    return jsonify({'error': 'Erro ao cancelar assinatura no gateway'}), 502


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
        reconciled = reconcile_tournament_labels(tournament_db_id)
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


@app.route('/admin/finance/coaches', methods=['GET'])
@require_admin
def admin_finance_coaches():
    import datetime
    period = request.args.get('period', datetime.date.today().strftime('%Y-%m'))
    payouts = get_coaches_with_payout_status(period)
    # upsert payment records for coaches with active students
    for p in payouts:
        if p['active_students'] > 0 and not p['payment_id']:
            pid = upsert_coach_payment(p['id'], period, p['active_students'], p['amount_cents'])
            p['payment_id'] = pid
            p['status'] = 'pending'
    total_pending = sum(p['amount_cents'] for p in payouts if p.get('status') == 'pending')
    return jsonify({'payouts': payouts, 'period': period, 'total_pending_cents': total_pending})


@app.route('/admin/finance/coaches/<int:payment_id>/pay', methods=['PATCH'])
@require_admin
def admin_mark_payment_paid(payment_id):
    mark_coach_payment_paid(payment_id)
    return jsonify({'ok': True})


@app.route('/admin/finance/export.csv', methods=['GET'])
@require_admin
def admin_finance_export():
    import datetime, io, csv
    from flask import Response
    period = request.args.get('period', datetime.date.today().strftime('%Y-%m'))
    payouts = get_coaches_with_payout_status(period)
    buf = io.StringIO()
    w   = csv.writer(buf)
    w.writerow(['Coach', 'Alunos Ativos', 'Valor (R$)', 'Status', 'Pago em'])
    for p in payouts:
        w.writerow([
            p.get('display_name') or p['username'],
            p['active_students'],
            f"{p['amount_cents'] / 100:.2f}",
            p.get('status', 'pending'),
            p.get('paid_at', ''),
        ])
    resp = Response(buf.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = f'attachment; filename=repasses-{period}.csv'
    return resp


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


# ── WhatsApp Webhook — BACK-016 ───────────────────────────────────────────────

WA_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
WA_VERIFY_TOKEN   = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'leaklab_wh_verify_2026')


@app.route('/whatsapp/webhook', methods=['GET'])
def whatsapp_verify():
    """Verificação do webhook pelo Meta Developer Portal."""
    mode      = request.args.get('hub.mode')
    token     = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == WA_VERIFY_TOKEN:
        log.info("WhatsApp webhook verified")
        return challenge, 200
    return jsonify({'error': 'Forbidden'}), 403


@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    """Recebe eventos de mensagem da Meta e despacha para o bot."""
    from leaklab.whatsapp_bot import handle_incoming
    try:
        body = request.get_json(force=True, silent=True) or {}
        for entry in body.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                phone_number_id = value.get('metadata', {}).get('phone_number_id', WA_PHONE_NUMBER_ID)
                for msg in value.get('messages', []):
                    from_number  = msg.get('from', '')
                    message_text = (msg.get('text') or {}).get('body', '')
                    if from_number and message_text:
                        handle_incoming(phone_number_id, from_number, message_text)
    except Exception as exc:
        log.error("WhatsApp webhook error: %s", exc)
    # Meta exige 200 imediato — sempre
    return jsonify({'status': 'ok'}), 200


@app.route('/profile/phone', methods=['PATCH'])
@require_auth
def update_phone():
    """Vincula/desvincula número de WhatsApp ao perfil do usuário logado."""
    data  = request.get_json(force=True, silent=True) or {}
    phone = data.get('phone', '').strip() or None
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
    return '<html><body style="font-family:sans-serif;text-align:center;padding:60px"><h2>Inscrição cancelada</h2><p>Você não receberá mais o digest semanal do LeakLabs.</p></body></html>', 200


@app.route('/admin/send-digest', methods=['POST'])
@require_admin
def admin_send_digest():
    result = run_weekly_digest()
    return jsonify(result)


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
    base_url = os.environ.get('APP_BASE_URL', 'https://leaklabs.ai')
    html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#0f1117;color:#f1f5f9;padding:40px">
<h2 style="color:#6366f1">Candidatura aprovada — LeakLabs.ai</h2>
<p>Olá, <strong>{app['username']}</strong>!</p>
<p>Sua candidatura como coach foi <strong style="color:#22c55e">aprovada</strong>.</p>
<p>Você já pode fazer login e configurar seu perfil:</p>
<p><a href="{base_url}/login" style="color:#6366f1">{base_url}/login</a></p>
{f'<p style="color:#9ca3af">Nota do admin: {note}</p>' if note else ''}
</body></html>"""
    send_transactional_email(app['email'], 'Candidatura aprovada — LeakLabs.ai', html)
    return jsonify({'ok': True})


@app.route('/admin/coach-applications/<int:app_id>/reject', methods=['POST'])
@require_admin
def admin_reject_coach_application(app_id):
    note = (request.get_json(silent=True) or {}).get('note', '')
    app  = reject_coach_application(app_id, note)
    if not app:
        return jsonify({'error': 'Candidatura não encontrada'}), 404
    if note:
        base_url = os.environ.get('APP_BASE_URL', 'https://leaklabs.ai')
        html = f"""<!DOCTYPE html><html><body style="font-family:sans-serif;background:#0f1117;color:#f1f5f9;padding:40px">
<h2 style="color:#6366f1">Atualização da candidatura — LeakLabs.ai</h2>
<p>Olá, <strong>{app['username']}</strong>.</p>
<p>Sua candidatura como coach não foi aprovada neste momento.</p>
<p style="color:#9ca3af">Motivo: {note}</p>
<p>Você pode entrar em contato pelo site para mais informações.</p>
</body></html>"""
        send_transactional_email(app['email'], 'Candidatura — LeakLabs.ai', html)
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

    dec = get_decision_spot(decision_id)
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

    # Truncate board to street-appropriate length (DB stores full board; hashes use street slice)
    _street_cards = {'flop': 3, 'turn': 4, 'river': 5}
    board_for_hash = board[:_street_cards.get(street, len(board))]

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
        return n

    # ── Node lookup: multiple fallback strategies ────────────────────────────
    node = None
    # a) Exact: with hero_hand + facing
    if hero_hand:
        _h = compute_spot_hash(street, position, board_for_hash, hero_hand, stack_bb, facing_bb)
        node = _valid_node_replayer(get_gto_node(_h))
    # b) Generic: no hero_hand, with facing
    if not node:
        _h = compute_spot_hash(street, position, board_for_hash, [], stack_bb, facing_bb)
        node = _valid_node_replayer(get_gto_node(_h))
    # c) Generic: no hero_hand, no facing (only when not facing a bet)
    if not node and facing_bb == 0:
        _h = compute_spot_hash(street, position, board_for_hash, [], stack_bb, 0.0)
        node = _valid_node_replayer(get_gto_node(_h))
    # fallback d (get_gto_node_by_spot) removido: hash algorithm divergente → falsos matches

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
                    position     = position,
                    hero_hand_type = h_type,
                    stack_bb     = stack_bb,
                    action_taken = player_action,
                    facing_size  = facing_bb,
                    vs_position  = (dec.get('villain_position') or ''),
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
    from leaklab.preflop_gto_ranges import _load, _stack_bucket, _expand_range, _norm_pos

    position = request.args.get('position', 'BTN')
    stack_bb = float(request.args.get('stack_bb', 30.0))

    pos    = _norm_pos(position)
    bucket = _stack_bucket(stack_bb)
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

    # vs_3bet
    vs3_raw = bk.get('vs_3bet', {})
    spot    = vs3_raw.get(f'{pos}_RFI_vs_3bet') or next(
        (v for k, v in vs3_raw.items() if k.endswith('_RFI_vs_3bet')), None
    )
    vs_3bet = None
    if spot:
        vs_3bet = {
            'hands_4bet':    sorted(_expand_range(spot.get('hands_4bet', ''))),
            'hands_call':    sorted(_expand_range(spot.get('hands_call', ''))),
            'pct_continua':  float(spot.get('pct_continua', 0)),
        }

    return jsonify({
        'position':     pos,
        'stack_bb':     round(stack_bb, 1),
        'stack_bucket': bucket,
        'rfi':          rfi,
        'vs_rfi':       vs_rfi,
        'vs_3bet':      vs_3bet,
    })


@app.route('/gto/strategy', methods=['POST'])
@require_auth
def gto_strategy():
    """
    Lookup GTO verificado para um spot específico.
    Só retorna dados com exploitability_pct confirmada pelo solver.

    Body: street, position, board[], hero_hand[], hero_stack_bb,
          action_seq (default 'rfi'), vs_position (default '')

    200 → found=True, dados verificados com exploitability_pct
    202 → found=False, spot enfileirado para solve
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

    result = lookup_gto(
        street=street, position=position, board=board,
        hero_hand=hero_hand, hero_stack_bb=hero_stack_bb,
        action_seq=action_seq, vs_position=vs_position,
        facing_size_bb=facing_size_bb,
        num_players=num_players,
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
    from database.repositories import request_gto_for_hand, get_decisions
    user_id = g.user_id
    body = request.get_json(force=True) or {}
    tournament_id = body.get('tournament_id')
    if not tournament_id:
        return jsonify({'error': 'tournament_id obrigatório'}), 400

    # Verificar acesso
    t = get_tournament(user_id, str(tournament_id))
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404

    result = request_gto_for_hand(t['id'], hand_id, user_id)
    status_map = {
        'pending':    'Na fila — análise será processada em breve.',
        'processing': 'Processando agora...',
        'done':       'Análise já concluída.',
        'error':      'Ocorreu um erro no processamento anterior.',
    }
    return jsonify({
        'queued':  result['inserted'],
        'status':  result['status'],
        'id':      result['id'],
        'message': status_map.get(result['status'], 'Na fila.'),
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
        last_done = _fetchone(conn, _adapt("""
            SELECT processed_at FROM gto_hand_requests
            WHERE status IN ('done','error')
            ORDER BY processed_at DESC LIMIT 1
        """))
        last_heartbeat = last_done['processed_at'] if last_done else None

        # ── Throughput: requests processed per hour (last 24h) ───────────────
        throughput_rows = _fetchall(conn, _adapt("""
            SELECT strftime('%Y-%m-%dT%H:00:00', processed_at) AS hour,
                   COUNT(*) AS n
            FROM gto_hand_requests
            WHERE status IN ('done','error')
              AND processed_at >= datetime('now', '-24 hours')
            GROUP BY hour
            ORDER BY hour ASC
        """))
        throughput = [{'hour': r['hour'], 'count': r['n']} for r in throughput_rows]

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

    finally:
        conn.close()

    return jsonify({
        'worker': {
            'active':         is_active,
            'last_heartbeat': last_heartbeat,
        },
        'hand_queue':   hand_counts,
        'solver_queue': solver_counts,
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
        affected_ids  = set()
        changes       = []

        for row in tournaments:
            tid = row['id']
            raw_row = conn.execute(
                "SELECT raw_text FROM tournaments WHERE id = ?", (tid,)
            ).fetchone()
            if not raw_row or not raw_row[0]:
                continue

            try:
                hands = parse_hand_history(raw_row[0])
            except Exception:
                continue

            seen: set = set()
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

                    db_row = conn.execute(
                        "SELECT id, label FROM decisions "
                        "WHERE hand_id = ? AND street = 'preflop' AND action_taken = ? LIMIT 1",
                        (hand_id, act)
                    ).fetchone()
                    if not db_row:
                        continue

                    did, old_label = db_row['id'], db_row['label']
                    total_checked += 1

                    try:
                        result    = evaluate_decision(di)
                        new_label = (result.get('evaluation') or {}).get('label') or old_label
                    except Exception:
                        continue

                    if new_label != old_label:
                        conn.execute(
                            "UPDATE decisions SET label = ? WHERE id = ?",
                            (new_label, did)
                        )
                        total_updated += 1
                        affected_ids.add(tid)
                        changes.append({
                            'tid': tid, 'hand_id': hand_id,
                            'action': act, 'old': old_label, 'new': new_label
                        })

        if affected_ids:
            conn.commit()
            for tid in affected_ids:
                std_row = conn.execute(
                    "SELECT COUNT(CASE WHEN label='standard' THEN 1 END)*100.0/COUNT(*) AS s, "
                    "AVG(score) AS a FROM decisions WHERE tournament_id = ?", (tid,)
                ).fetchone()
                if std_row:
                    conn.execute(
                        "UPDATE tournaments SET standard_pct=?, avg_score=? WHERE id=?",
                        (round(std_row[0], 2), round(std_row[1] or 0, 4), tid)
                    )
            conn.commit()

        return jsonify({
            'checked':  total_checked,
            'updated':  total_updated,
            'affected_tournaments': len(affected_ids),
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


@app.errorhandler(500)
def internal_error(e): return jsonify({'error': f'Erro interno do servidor: {e}'}), 500

@app.errorhandler(413)
def too_large(_): return jsonify({'error': 'Arquivo muito grande (limite: 5MB)'}), 413

@app.errorhandler(405)
def method_not_allowed(_): return jsonify({'error': 'Método não permitido'}), 405

@app.errorhandler(404)
def not_found(_): return jsonify({'error': 'Rota não encontrada'}), 404


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

        # Índice rápido: (street, action_taken) → decision_id
        def _norm(a):
            if not a: return ''
            a = a.rstrip('s') if a.endswith('s') else a
            return 'allin' if a in ('all-in', 'allin', 'jam', 'shove') else a
        db_index = {(_norm(d.get('street', '')), _norm(d.get('action_taken', ''))): d
                    for d in db_decisions}

        update_gto_hand_request(request_id, 'processing',
                                decisions_found=len(db_decisions))

        done = 0      # resolvidos agora pela primeira vez
        queued = 0    # enfileirados para o solver (não estavam na base)
        for di in build_decision_inputs_for_hand(target):
            if di['street'] not in ('flop', 'turn', 'river'):
                continue
            ctx = di.get('context', {})
            key = (_norm(di['street']), _norm(di.get('player_action', '') or ''))
            db_dec = db_index.get(key)
            if not db_dec:
                continue
            already_analyzed = bool(db_dec.get('gto_label'))
            # Não pula: re-analisa sempre para corrigir gto_action de nós parciais antigos

            spot = di.get('spot', {})
            gto = lookup_gto(
                street          = di['street'],
                position        = spot.get('position', ctx.get('position', '')),
                board           = spot.get('board', []),
                hero_hand       = di.get('hero_cards', []),
                hero_stack_bb   = spot.get('effectiveStackBb', ctx.get('heroStackBb', 20.0)),
                action_seq      = ctx.get('actionSeq', 'rfi'),
                vs_position     = spot.get('villainPosition', ctx.get('vsPosition', '')),
                facing_size_bb  = float(db_dec.get('facing_bet', 0) or 0),
                pot_bb          = float(spot.get('potSize', 0) or 0),
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
                    # Enfileira o spot correto (com facing real) para o solver resolver
                    try:
                        from leaklab.gto_utils import compute_spot_hash as _csh
                        from leaklab.gto_solver import _DEFAULT_RANGES, _DEFAULT_RANGE_WIDE, _priority, _solver_params_for_stack
                        import json as _json2
                        _spot2 = di.get('spot', {})
                        _ctx2  = di.get('context', {})
                        _board2 = di.get('board', []) or _spot2.get('board', [])
                        _pos2   = (_spot2.get('position') or _ctx2.get('position') or '').upper()
                        _vs2    = (_spot2.get('villainPosition') or _ctx2.get('vsPosition') or '').upper()
                        _stack2 = float(_spot2.get('effectiveStackBb') or _ctx2.get('heroStackBb') or 20)
                        _hand2  = di.get('hero_cards', [])
                        _hash2  = _csh(di['street'], _pos2, _board2, _hand2, _stack2, _facing)
                        _params2 = _solver_params_for_stack(_stack2)
                        _payload2 = _json2.dumps({
                            'street': di['street'], 'board': _board2, 'position': _pos2,
                            'hero_hand': _hand2, 'hero_stack_bb': _stack2, 'facing_size_bb': _facing,
                            'oop_range': _DEFAULT_RANGES.get(_vs2, _DEFAULT_RANGE_WIDE),
                            'ip_range':  _DEFAULT_RANGES.get(_pos2, _DEFAULT_RANGE_WIDE),
                            'pot_bb': float(_spot2.get('potSize') or _facing * 2 + 2 or 4.0),
                            'effective_stack_bb':        _params2['effective_stack_bb'],
                            'max_iterations':            _params2['max_iterations'],
                            'target_exploitability_pct': _params2['target_exploitability_pct'],
                        }, sort_keys=True)
                        from database.repositories import enqueue_solver_spot as _enq2
                        _enq2(_hash2, _payload2, priority=_priority(di['street']))
                    except Exception:
                        pass
                    queued += 1  # trata como pendente — spot correto enfileirado para o solver
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
                # Spot não está na base — lookup_gto enfileirou para o solver local
                # se is_simple_spot=False (stack alto, turn/river), marcar para
                # fallback ao GTO Wizard (processado via fallback_gto_wizard.py)
                _facing2  = float(db_dec.get('facing_bet', 0) or 0)
                _stack2   = float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 20)
                _street2  = di.get('street', 'flop')
                try:
                    from leaklab.gto_solver import is_simple_spot as _is_simple
                    _board2 = spot.get('board', [])
                    if not _is_simple(_street2, _board2, _stack2, _facing2):
                        # Solver local não vai resolver → marca para fallback wizard
                        conn_flag = get_conn()
                        try:
                            conn_flag.execute(_adapt("""
                                UPDATE decisions SET gto_label = 'wizard_pending'
                                WHERE id = ?
                            """), (db_dec['id'],))
                            conn_flag.commit()
                        finally:
                            conn_flag.close()
                except Exception:
                    pass
                queued += 1

        # done>0: resolveu novos spots agora → done
        # queued>0 e done=0: spots enfileirados, sem resolução imediata → solver_queued
        # ambos zero: nada para processar (todos já tinham label ou sem match) → done
        final_status = 'solver_queued' if queued > 0 and done == 0 else 'done'
        return final_status, None, done, queued

    except Exception as exc:
        log.exception("GTO hand worker error req_id=%s", request_id)
        return 'error', str(exc), 0, 0


def _mark_failed_solver_jobs_as_wizard_pending() -> int:
    """
    Varre gto_solver_queue com status='failed' e marca as decisões
    correspondentes como wizard_pending para o fallback ao GTO Wizard.
    Retorna número de decisões marcadas.
    """
    from database.schema import get_conn
    from database.repositories import _fetchall, _adapt
    conn = get_conn()
    marked = 0
    try:
        failed_jobs = _fetchall(conn, _adapt("""
            SELECT spot_hash, spot_json FROM gto_solver_queue WHERE status = 'failed'
        """))
        for job in failed_jobs:
            try:
                import json as _j
                spot = _j.loads(job['spot_json'] or '{}')
                street   = spot.get('street', '')
                board    = spot.get('board', [])
                position = spot.get('position', '')
                stack    = float(spot.get('hero_stack_bb') or spot.get('effective_stack_bb') or 0)
                facing   = float(spot.get('facing_size_bb', 0) or 0)
                if not street or not position or stack <= 0:
                    continue
                # Encontrar decisões que correspondam a este spot
                conn.execute(_adapt("""
                    UPDATE decisions SET gto_label = 'wizard_pending'
                    WHERE street = ? AND position = ?
                      AND (gto_label IS NULL OR gto_label = 'wizard_pending')
                      AND ABS(CAST(stack_bb AS REAL) - ?) < 5
                      AND ABS(COALESCE(CAST(facing_bet AS REAL), 0) - ?) < 1
                """), (street, position, stack, facing))
                marked += conn.total_changes
            except Exception:
                continue
        conn.commit()
    finally:
        conn.close()
    return marked


def _gto_hand_worker_loop():
    """Worker em background: processa gto_hand_requests pendentes a cada 30s.
    A cada ciclo também varre jobs falhos do cloud solver e marca as decisões
    correspondentes como wizard_pending para fallback automático ao GTO Wizard.
    """
    from database.repositories import (
        get_pending_gto_hand_requests, update_gto_hand_request,
    )
    time.sleep(10)  # aguardar app inicializar
    while True:
        try:
            pending = get_pending_gto_hand_requests(limit=10)
            for req in pending:
                log.info("GTO hand worker: processando req_id=%s hand=%s", req['id'], req['hand_id'])
                status, err, n_done, n_queued = _process_gto_hand_request(dict(req))
                update_gto_hand_request(
                    req['id'], status,
                    decisions_done=n_done,
                    error_msg=err,
                )
                log.info("GTO hand worker: req_id=%s → %s (done=%s queued=%s)", req['id'], status, n_done, n_queued)

            # Fallback: marcar decisões cujos jobs do cloud solver falharam
            wizard_marked = _mark_failed_solver_jobs_as_wizard_pending()
            if wizard_marked:
                log.info("GTO fallback: %d decisoes marcadas como wizard_pending", wizard_marked)

            # Intervalo adaptativo: ciclo rápido se havia pendentes, normal se fila vazia
            time.sleep(5 if pending else 30)
        except Exception:
            log.exception("GTO hand worker loop error")
            time.sleep(30)


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


def _enqueue_postflop_spots(results: list) -> None:
    """
    Enfileira na gto_solver_queue todos os spots postflop do upload que ainda
    não existam em gto_nodes. Roda em background — não bloqueia a resposta ao usuário.
    """
    from leaklab.gto_utils import compute_spot_hash
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
            board  = d.get('board', [])
            hero_h = d.get('hero_cards', [])
            pos    = spot.get('position', ctx.get('position', '')).upper()
            stack  = float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 20)
            _level_bb = float(d.get('level_bb') or 1) or 1
            facing = round(float(spot.get('facingSize') or 0) / _level_bb, 2)

            spot_hash = compute_spot_hash(d['street'], pos, board, hero_h, stack, facing)
            if get_gto_node(spot_hash):
                already += 1
                continue

            from leaklab.gto_solver import _DEFAULT_RANGES, _DEFAULT_RANGE_WIDE, _priority, _solver_params_for_stack
            vs_pos   = spot.get('villainPosition', ctx.get('vsPosition', '')).upper()
            pot_bb   = float(spot.get('potSize') or facing * 2 + 2 or 4.0)
            _params  = _solver_params_for_stack(stack)
            payload  = _json.dumps({
                'street':                    d['street'],
                'board':                     board,
                'position':                  pos,
                'hero_hand':                 hero_h,
                'hero_stack_bb':             stack,
                'facing_size_bb':            facing,
                'oop_range':                 _DEFAULT_RANGES.get(vs_pos, _DEFAULT_RANGE_WIDE),
                'ip_range':                  _DEFAULT_RANGES.get(pos,    _DEFAULT_RANGE_WIDE),
                'pot_bb':                    pot_bb,
                'effective_stack_bb':        _params['effective_stack_bb'],  # capped for tree size
                'max_iterations':            _params['max_iterations'],
                'target_exploitability_pct': _params['target_exploitability_pct'],
                '_meta': {'position': pos, 'vs_position': vs_pos, 'hero_hand': hero_h,
                          'hero_stack_bb': stack, 'facing_size_bb': facing,
                          'street': d['street'], 'board': board},
            }, sort_keys=True)

            if enqueue_solver_spot(spot_hash, payload, priority=_priority(d['street'])):
                enqueued += 1
        except Exception:
            pass

    log.info("Upload GTO enqueue: %s novos spots enfileirados, %s já resolvidos", enqueued, already)


def _solver_queue_worker_loop():
    """Worker em background: roda o solver Rust nos spots pendentes da gto_solver_queue a cada 60s."""
    from leaklab.gto_solver import run_solver_worker
    time.sleep(15)  # aguardar app inicializar
    tick = 0
    while True:
        try:
            from database.schema import get_conn as _gc
            conn = _gc()
            # Reseta spots que ficaram em 'running' > 10 min (backend restart, crash, etc.)
            conn.execute("UPDATE gto_solver_queue SET status='pending' WHERE status='running' AND requested_at < datetime('now', '-10 minutes')")
            conn.commit()
            stats = {r[0]: r[1] for r in conn.execute("SELECT status, COUNT(*) FROM gto_solver_queue GROUP BY status").fetchall()}
            conn.close()
            pending = stats.get('pending', 0)
            tick += 1
            log.info("Solver queue [tick %s]: pending=%s running=%s done=%s failed=%s",
                     tick, pending, stats.get('running', 0), stats.get('done', 0), stats.get('failed', 0))
            if pending > 0:
                result = run_solver_worker(max_jobs=5)
                log.info("Solver queue worker resultado: %s", result)
        except Exception:
            log.exception("Solver queue worker loop error")
        time.sleep(60)


if __name__ == '__main__':
    _worker = threading.Thread(target=_gto_hand_worker_loop, daemon=True, name='gto-hand-worker')
    _worker.start()
    _solver_worker = threading.Thread(target=_solver_queue_worker_loop, daemon=True, name='gto-solver-worker')
    _solver_worker.start()
    try:
        from leaklab.gto_wizard_client import start_background_refresher as _gw_start
        _gw_start()
    except Exception:
        pass
    app.run(debug=True, port=5000)
