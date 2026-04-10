"""
LeakLab API v2 — com persistência SQLite e autenticação JWT.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, request, jsonify, g
from flask_cors import CORS

from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision
from leaklab.mtt_context import build_mtt_context
from leaklab.session_metrics import build_session_metrics
from leaklab.leak_correlator import correlate_leaks
from leaklab.llm_explainer import explain_decisions, generate_tournament_summary

from database.schema import init_db
from database.repositories import (
    create_user, verify_password, get_user_by_email,
    save_tournament, save_decisions, get_tournaments,
    get_tournament, get_decisions, update_llm_summary,
    get_evolution_metrics, get_leak_summary, get_icm_performance,
    get_students,
    # Coach system
    assign_invite_key, get_coach_by_invite_key, link_student_to_coach,
    upsert_coach_profile, get_coach_profile, get_public_coaches,
    get_coach_impact_metrics, recommend_coaches_for_leaks,
)
from database.auth import generate_token, require_auth, require_coach

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
CORS(app, resources={r"/*": {
    "origins": "*",
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
}})

# Inicializar banco ao subir
init_db()

# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    email    = data.get('email',    '').strip().lower()
    password = data.get('password', '')
    role     = data.get('role', 'player')

    if not all([username, email, password]):
        return jsonify({'error': 'username, email e password são obrigatórios'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Senha deve ter pelo menos 6 caracteres'}), 400
    if get_user_by_email(email):
        return jsonify({'error': 'Email já cadastrado'}), 409

    try:
        user_id = create_user(username, email, password, role)
        token   = generate_token(user_id, role)
        return jsonify({'token': token, 'user_id': user_id, 'role': role}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/auth/login', methods=['POST'])
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
    return jsonify({
        'user_id':  g.user['id'],
        'username': g.user['username'],
        'email':    g.user['email'],
        'role':     g.user['role'],
    })


# ── Análise + persistência ────────────────────────────────────────────────────

@app.route('/analyze', methods=['POST'])
@require_auth
def analyze():
    content = _extract_content(request)
    if not content:
        return jsonify({'error': 'Conteúdo ausente'}), 400

    try:
        hands = parse_pokerstars_file_from_text(content)
    except Exception as e:
        return jsonify({'error': f'Erro ao parsear: {str(e)}'}), 422

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
    played_at     = _extract_date(hands[0].raw_text if hasattr(hands[0],'raw_text') else '')

    # Persistir
    t_db_id = save_tournament(
        user_id=g.user_id,
        tournament_id=tournament_id,
        hero=hero,
        metrics=metrics,
        site=site,
        played_at=played_at,
    )
    save_decisions(t_db_id, results)

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
        'session_id':    str(uuid.uuid4()),
        'tournament_db_id': t_db_id,
        'hero':          hero,
        'tournament_id': tournament_id,
        'total_hands':   len(hands),
        'parse_errors':  len(errors),
        'metrics':       metrics,
        'leaks':         leaks,
        'hands':         hand_results,
    })


@app.route('/analyze/tournament-summary', methods=['POST'])
@require_auth
def tournament_summary():
    content = _extract_content(request)
    if not content:
        return jsonify({'error': 'Conteúdo ausente'}), 400

    try:
        hands = parse_pokerstars_file_from_text(content)
    except Exception as e:
        return jsonify({'error': str(e)}), 422

    results, _, _ = _analyze_hands(hands)
    if not results:
        return jsonify({'error': 'Nenhuma decisão encontrada'}), 422

    hero = hands[0].hero or 'Hero'
    summary = generate_tournament_summary(results, len(hands), hero)

    # Persistir no torneio se existir
    t_id = hands[0].tournament_id if hands else None
    if t_id:
        t = get_tournament(g.user_id, t_id)
        if t:
            update_llm_summary(t['id'], summary)

    return jsonify({
        'hero':            hero,
        'summary':         summary,
        'total_hands':     len(hands),
        'total_decisions': len(results),
    })


# ── Histórico e evolução ──────────────────────────────────────────────────────

@app.route('/history/tournaments', methods=['GET'])
@require_auth
def history_tournaments():
    limit = int(request.args.get('limit', 50))
    tournaments = get_tournaments(g.user_id, limit)
    return jsonify({'tournaments': tournaments})


@app.route('/history/tournament/<tournament_id>', methods=['GET'])
@require_auth
def history_tournament(tournament_id):
    t = get_tournament(g.user_id, tournament_id)
    if not t:
        return jsonify({'error': 'Torneio não encontrado'}), 404
    decisions = get_decisions(t['id'])
    return jsonify({'tournament': t, 'decisions': decisions})


@app.route('/history/evolution', methods=['GET'])
@require_auth
def history_evolution():
    days = int(request.args.get('days', 30))
    return jsonify({
        'evolution': get_evolution_metrics(g.user_id, days),
        'leaks':     get_leak_summary(g.user_id, days),
        'icm':       get_icm_performance(g.user_id, days),
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
    return jsonify({'status': 'ok', 'version': '2.0', 'db': 'sqlite'})


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
        try:
            return req.files['file'].read().decode('utf-8', errors='replace')
        except Exception:
            return None
    return req.form.get('content')


def _analyze_hands(hands):
    results, hand_results, errors = [], {}, []
    for hand in hands:
        try:
            mtt    = build_mtt_context(hand)
            inputs = build_decision_inputs_for_hand(hand)
            decisions = []
            for di in inputs:
                r = evaluate_decision(di)
                enriched = {
                    **r,
                    'street':       di['street'],
                    'context':      di['context'],
                    'math':         di['math'],
                    'hero_cards':   hand.hero_cards,
                    'board':        hand.board or [],
                    'draw_profile': di['math'].get('drawProfile', ''),
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
    if 'PokerStars' in raw: return 'pokerstars'
    if 'GGPoker'   in raw: return 'ggpoker'
    if '888'       in raw: return '888poker'
    return 'unknown'


def _extract_date(raw: str) -> str | None:
    import re
    m = re.search(r'(\d{4}/\d{2}/\d{2})', raw)
    return m.group(1).replace('/', '-') if m else None


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
        if not profile:
            return jsonify({'error': 'Perfil não encontrado'}), 404
        return jsonify(profile)

    # POST — criar/atualizar
    data = request.get_json(silent=True) or {}
    profile = upsert_coach_profile(
        user_id=g.user_id,
        display_name=data.get('display_name', ''),
        bio=data.get('bio', ''),
        specialties=data.get('specialties', []),
        contact_email=data.get('contact_email'),
        contact_link=data.get('contact_link'),
        is_public=data.get('is_public', True),
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
    """Lista coaches públicos (sem auth)."""
    specialty = request.args.get('specialty')
    limit     = int(request.args.get('limit', 20))
    coaches   = get_public_coaches(specialty=specialty, limit=limit)
    return jsonify({'coaches': coaches})


@app.route('/coaches/<int:coach_user_id>', methods=['GET'])
def public_coach_profile(coach_user_id):
    """Perfil público de um coach específico."""
    profile = get_coach_profile(coach_user_id)
    if not profile or not profile.get('is_public'):
        return jsonify({'error': 'Coach não encontrado'}), 404
    # Remover dados sensíveis do perfil público
    safe = {k: v for k, v in profile.items()
            if k not in ('password_hash', 'email') or k == 'contact_email'}
    return jsonify(safe)


# Redirecionar o endpoint antigo de coach/students para o novo
@app.route('/coach/students-legacy', methods=['GET'])
@require_coach
def coach_students_legacy():
    return coach_students_v2()


@app.route('/analyze/hand-coach', methods=['POST'])
@require_auth
def hand_coach():
    """
    Análise profunda de uma mão específica pelo Coach IA.
    Recebe os dados completos da mão e retorna análise detalhada com:
    - Matemática (equity, pot odds, EV estimado)
    - Teoria (conceitos violados)
    - Ação correta com justificativa
    - Dica prática aplicável
    """
    data = request.get_json(silent=True) or {}
    hand_data = data.get('hand')
    if not hand_data:
        return jsonify({'error': 'Dados da mão ausentes'}), 400

    try:
        from leaklab.llm_explainer import _build_payload, _call_llm_api
        import json as _json

        # Filtrar só decisões com erro para análise
        decisions = hand_data.get('decisions', hand_data.get('decs', []))
        # Normalizar formato
        norm_decs = []
        for d in decisions:
            label = d.get('l') or d.get('label') or                     (d.get('evaluation') or {}).get('label', 'standard')
            score = d.get('sc') or d.get('score') or                     (d.get('evaluation') or {}).get('mistakeScore', 0)
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

        return jsonify({
            'hand_id':   hand_data.get('id', ''),
            'decisions': len(norm_decs),
            'analyses':  analyses,
        })

    except Exception as e:
        # Fallback template se LLM falhar
        return jsonify({
            'hand_id':  hand_data.get('id', ''),
            'analyses': [_template_hand_analysis(d) for d in decisions[:1]],
            'note':     'Análise gerada via template (LLM indisponível)',
        })


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

@app.errorhandler(413)
def too_large(_): return jsonify({'error': 'Arquivo muito grande (limite: 5MB)'}), 413

@app.errorhandler(405)
def method_not_allowed(_): return jsonify({'error': 'Método não permitido'}), 405

@app.errorhandler(404)
def not_found(_): return jsonify({'error': 'Rota não encontrada'}), 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)
