"""
PokerLeakLab API v2 — com persistência SQLite e autenticação JWT.
"""
from __future__ import annotations
import sys, os, re
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent  # backend/
sys.path.insert(0, str(_BASE))

from dotenv import load_dotenv
load_dotenv(_BASE / '.env')

import logging
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

log = logging.getLogger(__name__)

from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision
from leaklab.mtt_context import build_mtt_context
from leaklab.session_metrics import build_session_metrics
from leaklab.leak_correlator import correlate_leaks
from leaklab.llm_explainer import explain_decisions, generate_tournament_summary, coach_chat_reply

from database.schema import init_db
from database.repositories import (
    create_user, verify_password, get_user_by_email, get_user_by_id, get_user_by_username,
    save_tournament, save_decisions, get_tournaments,
    get_tournament, get_tournament_by_db_id, get_decisions, update_llm_summary,
    get_llm_cache, set_llm_cache,
    get_evolution_metrics, get_leak_summary, get_leak_roi_impact,
    get_pressure_profile, get_confidence_drift,
    get_drill_spots, save_drill_session, get_drill_stats, get_decision_for_drill,
    get_icm_performance, get_breakdown, get_player_stats,
    get_player_level,
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
    get_phase_analysis, get_texture_analysis,
    # Sprint C — BACK-014 + BACK-017: admin panel + revenue share
    get_admin_dashboard_stats, get_all_users, get_all_users_count, update_user_admin,
    get_coaches_with_payout_status, upsert_coach_payment, mark_coach_payment_paid,
    get_coach_finance_summary, get_coach_finance_students, get_coach_finance_history,
    get_admin_activity_logs,
    # Sprint D — BACK-016: WhatsApp
    get_user_by_phone, update_user_phone,
)
from database.auth import generate_token, require_auth, require_coach, require_admin
from leaklab.content_moderation import sanitize_llm_input, moderate_text
from leaklab.stripe_gateway import (
    create_subscription, cancel_subscription, get_subscription, get_payment,
    validate_webhook, PLAN_AMOUNTS, STRIPE_WEBHOOK_SECRET,
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
CORS(app,
     resources={r"/*": {"origins": "*"}},
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
    response.headers.setdefault('Access-Control-Allow-Origin',  '*')
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

    if role not in ('player', 'coach'):
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


@app.route('/auth/login', methods=['POST'])
@limiter.limit("15 per minute")
def login():
    data     = request.get_json(silent=True) or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = verify_password(email, password)
    if not user:
        return jsonify({'error': 'Credenciais inválidas'}), 401

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
        'whatsapp_phone':       g.user.get('whatsapp_phone'),
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
    )
    save_decisions(t_db_id, results)
    try:
        increment_tournament_count(g.user_id)
    except Exception:
        pass


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


@app.route('/history/evolution', methods=['GET'])
@require_auth
def history_evolution():
    days = int(request.args.get('days', 30))
    return jsonify({
        'evolution': get_evolution_metrics(g.user_id, days),
        'leaks':     get_leak_summary(g.user_id, days),
        'icm':       get_icm_performance(g.user_id, days),
    })


@app.route('/history/breakdown', methods=['GET'])
@require_auth
def history_breakdown():
    days = int(request.args.get('days', 90))
    return jsonify(get_breakdown(g.user_id, days))


@app.route('/metrics/player-stats', methods=['GET'])
@require_auth
def player_stats():
    days = int(request.args.get('days', 90))
    return jsonify(get_player_stats(g.user_id, days))


@app.route('/metrics/level', methods=['GET'])
@require_auth
def player_level():
    return jsonify(get_player_level(g.user_id))


@app.route('/player/leak-roi', methods=['GET'])
@require_auth
def player_leak_roi():
    """PERF-001+002 — Leaks com ROI estimado, priority score e trend."""
    days = int(request.args.get('days', 90))
    return jsonify({'leaks': get_leak_roi_impact(g.user_id, days)})


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

    best_action    = row['best_action']
    original_score = row['score']
    # Evaluation: correct if new action matches best action
    is_correct = new_action == best_action
    new_score  = 0.02 if is_correct else original_score

    result = save_drill_session(
        user_id=g.user_id,
        decision_id=decision_id,
        new_action=new_action,
        new_score=new_score,
        original_score=original_score,
    )
    return jsonify({
        'is_correct':     is_correct,
        'best_action':    best_action,
        'new_action':     new_action,
        'new_score':      new_score,
        'original_score': original_score,
        'delta':          result['delta'],
    })


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

    days     = 90
    leaks    = get_leak_summary(g.user_id, days) or []
    evolution = get_evolution_metrics(g.user_id, days) or []
    hero     = g.user.get('username', 'Jogador')

    try:
        reply = coach_chat_reply(message, leaks, evolution, hero=hero)
        return jsonify({'reply': reply})
    except Exception as e:
        log.exception("coach_chat error")
        return jsonify({'error': 'Coach temporariamente indisponível'}), 500


@app.route('/coach/context', methods=['GET'])
@require_auth
def coach_context():
    days      = 90
    leaks     = get_leak_summary(g.user_id, days) or []
    evolution = get_evolution_metrics(g.user_id, days) or []
    tourns    = get_tournaments(g.user_id, limit=200)

    total_hands = sum(t.get('hands_count', 0) for t in tourns)

    avg_scores = [e['avg_score'] for e in evolution if e.get('avg_score') is not None]
    avg_score  = round(sum(avg_scores) / len(avg_scores), 4) if avg_scores else None

    std_pcts    = [e['standard_pct'] for e in evolution if e.get('standard_pct') is not None]
    standard_pct = round(sum(std_pcts) / len(std_pcts), 4) if std_pcts else None

    return jsonify({
        'hands_analyzed':       total_hands,
        'tournaments_analyzed': len(tourns),
        'top_leaks':            [{'spot': l['spot'], 'avg_score': l['avg_score'], 'n': l['n']} for l in leaks[:5]],
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
    days = int(request.args.get('days', 30))
    return jsonify({
        'student_id': student_id,
        'evolution':  get_evolution_metrics(student_id, days),
        'leaks':      get_leak_summary(student_id, days),
        'icm':        get_icm_performance(student_id, days),
        'tournaments':get_tournaments(student_id),
    })


# ── Util endpoints (sem auth — para o frontend offline) ──────────────────────

@app.route('/health', methods=['GET'])
def health():
    import os
    db_url = os.environ.get('DATABASE_URL', '')
    db_type = 'postgres' if db_url else 'sqlite'
    return jsonify({'status': 'ok', 'version': '2.0', 'db': db_type, 'db_url_set': bool(db_url)})


@app.route('/analyze/guest', methods=['POST'])
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

    # ── PokerStars buy-in: '$0.98+$0.12' ─────────────────────────────────────
    m = re.search(r'\$(\d+\.?\d*)\+\$(\d+\.?\d*)', raw)
    if m:
        result['buy_in'] = round(float(m.group(1)) + float(m.group(2)), 2)

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
    if hero:
        m = re.search(
            re.escape(hero) + r'.*?finished.*?(\d+)[a-z]{2} place.*?received \$(\d+\.?\d*)',
            raw, re.IGNORECASE
        )
        if m:
            result['place'] = int(m.group(1))
            result['prize'] = float(m.group(2))
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
    )
    # Garantir que tem chave de convite
    key = assign_invite_key(g.user_id)
    profile['invite_key'] = key
    return jsonify(profile)


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
        days = int(request.args.get('days', 90))
        leaks    = get_leak_summary(student_id, days)    or []
        evolution = get_evolution_metrics(student_id, days) or []
        icm      = get_icm_performance(student_id, days)  or {}
        if not leaks and not evolution:
            return jsonify({'error': 'Aluno sem dados suficientes'}), 400
        tourns = get_tournaments(student_id, limit=1)
        hero = tourns[0]['hero'] if tourns else 'Aluno'
        force_new = request.args.get('new') == '1'
        plan = generate_study_plan(leaks, evolution, icm, hero=hero, user_id=student_id, force_new=force_new)
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
    try:
        from leaklab.pipeline import build_decision_inputs_for_hand
        from leaklab.decision_engine_v11 import evaluate_decision as _eval
        live_decisions = []
        for di in build_decision_inputs_for_hand(target):
            r = _eval(di)
            live_decisions.append({
                'hand_id': str(target.hand_id), 'street': di['street'],
                'action_taken': r.get('actionTaken', ''), 'best_action': r.get('bestAction', ''),
                'label': r['evaluation']['label'], 'score': r['evaluation']['mistakeScore'],
                'context': di.get('context', {}), 'math': di.get('math', {}),
                'breakdown': r['evaluation'].get('scoreBreakdown', {}),
            })
        hand_decisions = live_decisions
    except Exception:
        decisions_db = get_decisions(t['id'])
        hand_decisions = [d for d in decisions_db if str(d.get('hand_id')) == str(hand_id)]
    replay = _build_replay_data(target, hand_decisions, t.get('hero', target.hero))
    # Attach coach annotations for decisions in this hand
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

        days = int(request.args.get('days', 90))

        leaks     = get_leak_summary(g.user_id, days)     or []
        evolution = get_evolution_metrics(g.user_id, days) or []
        icm       = get_icm_performance(g.user_id, days)   or {}

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

        plan = generate_study_plan(leaks, evolution, icm, hero=hero, user_id=g.user_id, force_new=force_new)

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


@app.route('/replay/<tournament_id>/<hand_id>', methods=['GET'])
@require_auth
def get_replay(tournament_id, hand_id):
    """Constrói dados de replay para uma mão específica."""
    import re as _re

    t = get_tournament(g.user_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404

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

    # Re-executar o engine ao vivo para garantir scores/labels atualizados
    # O banco pode ter dados de versões antigas do engine com bugs corrigidos
    try:
        from leaklab.pipeline import build_decision_inputs_for_hand
        from leaklab.decision_engine_v11 import evaluate_decision as _eval
        live_decisions = []
        for di in build_decision_inputs_for_hand(target):
            r = _eval(di)
            live_decisions.append({
                'hand_id':      str(target.hand_id),
                'street':       di['street'],
                'action_taken': r.get('actionTaken', ''),
                'best_action':  r.get('bestAction', ''),
                'label':        r['evaluation']['label'],
                'score':        r['evaluation']['mistakeScore'],
                'context':      di.get('context', {}),
                'math':         di.get('math', {}),
                'breakdown':    r['evaluation'].get('scoreBreakdown', {}),
            })
        hand_decisions = live_decisions
    except Exception:
        # Fallback para dados do banco se engine falhar
        decisions_db   = get_decisions(t['id'])
        hand_decisions = [d for d in decisions_db if str(d.get('hand_id')) == str(hand_id)]

    # Construir replay data
    replay = _build_replay_data(target, hand_decisions, t.get('hero', target.hero))

    # Incluir anotações do coach para o aluno visualizar no replay
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

    # Extrair seats e stacks do raw_text
    seats = {}
    for line in hand.raw_text.split('\n'):
        m = _re.match(r'Seat (\d+): (.+) \((\d+) in chips\)', line)
        if m:
            seats[int(m.group(1))] = {
                'player': m.group(2).strip(),
                'stack':  int(m.group(3))
            }
    if not seats:
        return {'error': 'Seats não encontrados'}

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
    def _norm(a): return a.rstrip('s') if a and a.endswith('s') else (a or '')

    error_map = {}
    for d in decisions_db:
        # Só marcar como erro se realmente é um erro — ignorar 'standard'
        if d.get('label', 'standard') in ('clear_mistake', 'small_mistake', 'marginal'):
            key = (d.get('street', ''), _norm(d.get('action_taken', '')))
            error_map[key] = d

    # Re-rodar o engine para pegar contexto completo (pot odds, equity, ICM)
    try:
        from leaklab.pipeline import build_decision_inputs_for_hand
        from leaklab.decision_engine_v11 import evaluate_decision
        engine_inputs = build_decision_inputs_for_hand(hand)
        for di in engine_inputs:
            r   = evaluate_decision(di)
            key = (di['street'], _norm(r.get('actionTaken', '')))
            if key in error_map:
                ctx  = di.get('context', {})
                math = di.get('math', {})
                error_map[key]['context'] = ctx
                error_map[key]['math']    = math
                error_map[key]['breakdown'] = r['evaluation'].get('scoreBreakdown', {})
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

        if action.action in ('calls', 'bets', 'raises') and amt:
            # Para raises: "raises X to Y" — X é o incremento, Y é o total colocado
            # O total que entra no pot é Y (não X), menos o que o jogador já tinha apostado
            if action.action == 'raises':
                m_to = _re.search(r'raises \d+ to (\d+)', action.raw or '')
                total_placed = int(m_to.group(1)) if m_to else amt
                already_in   = bets_r.get(pseat, 0)
                real_addition = total_placed - already_in
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
        decision = error_map.get(err_key) if action.player == hero else None

        # Dados extras do erro para o popup do replayer
        err_extra = {}
        if decision:
            ctx   = decision.get('context', {})
            math  = decision.get('math', {})
            bd    = decision.get('breakdown', {})
            err_extra = {
                'pot_odds_equity': math.get('potOddsEquity'),
                'hand_equity':     math.get('estimatedHandEquity'),
                'draw_profile':    math.get('drawProfile', 'none'),
                'm_ratio':         ctx.get('mRatio'),
                'icm_pressure':    ctx.get('icmPressure'),
                'hero_stack_bb':   ctx.get('heroStackBb'),
                'math_penalty':    bd.get('mathPenalty', 0),
                'range_penalty':   bd.get('rangePenalty', 0),
                'context_penalty': bd.get('contextPenalty', 0),
            }

        timeline.append(snap({
            'type':           'action',
            'player':         action.player,
            'seat':           pseat,
            'action':         _normalize_action(action.action),
            'amount':         amt,
            'is_hero':        action.player == hero,
            'is_error':       decision is not None and decision.get('label','standard') in ('clear_mistake','small_mistake','marginal'),
            'error_label':    decision.get('label')       if decision else None,
            'error_score':    round(float(decision.get('score', 0)), 3) if decision else None,
            'best_action':    decision.get('best_action')  if decision else None,
            'desc':           f"{action.player}: {_normalize_action(action.action)}"
                                + (f' {int(amt)}' if amt else ''),
            'revealed_cards': dict(current_revealed) if current_revealed else None,
            **err_extra,
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
            'type':          'showdown',
            'desc':          'Conclusão da mão',
            'summary':        summary,
            'revealed_cards': revealed,   # {seat_num_str: ["Ah","Kd"]}
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
        'seats':         {s: {'player': seats[s]['player'],
                              'stack':  seats[s]['stack'],
                              'pos':    positions[s]} for s in seats},
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


@app.errorhandler(500)
def internal_error(e): return jsonify({'error': f'Erro interno do servidor: {e}'}), 500

@app.errorhandler(413)
def too_large(_): return jsonify({'error': 'Arquivo muito grande (limite: 5MB)'}), 413

@app.errorhandler(405)
def method_not_allowed(_): return jsonify({'error': 'Método não permitido'}), 405

@app.errorhandler(404)
def not_found(_): return jsonify({'error': 'Rota não encontrada'}), 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)
