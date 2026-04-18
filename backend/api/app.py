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
    get_llm_cache, set_llm_cache,
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
    played_at  = _extract_date(hands[0].raw_text if hasattr(hands[0],'raw_text') else '')
    raw_full   = '\n'.join(h.raw_text for h in hands if hasattr(h,'raw_text'))
    financials = _extract_financials(raw_full, hero)

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
        raw_text=raw_full,           # salvar para replay futuro
    )
    save_decisions(t_db_id, results)

    # Invalidar cache do plano de estudos (dados mudaram)
    try:
        from database.schema import get_conn as _gc
        conn = _gc()
        conn.execute(
            "DELETE FROM llm_cache WHERE user_id=? AND cache_key LIKE 'study_plan:%'",
            (g.user_id,)
        )
        conn.commit()
        conn.close()
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
    # Garantir que datas sejam strings ISO (Postgres retorna datetime.date)
    for t in tournaments:
        for field in ('played_at', 'imported_at'):
            val = t.get(field)
            if val is not None and not isinstance(val, str):
                t[field] = str(val)[:10]  # YYYY-MM-DD
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


def _extract_financials(raw: str, hero: str) -> dict:
    """
    Extrai buy-in e prêmio do hero do hand history.
    Retorna dict com buy_in, prize, profit, place.
    """
    import re
    result = {'buy_in': None, 'prize': None, 'profit': None, 'place': None}

    # Buy-in: '$0.98+$0.12' ou '$10+$1' etc.
    m = re.search(r'\$(\d+\.?\d*)\+\$(\d+\.?\d*)', raw)
    if m:
        result['buy_in'] = round(float(m.group(1)) + float(m.group(2)), 2)

    # Resultado do hero: "phpro finished the tournament in 3rd place and received $23.29"
    if hero:
        # Com prêmio
        m = re.search(
            re.escape(hero) + r'.*?finished.*?(\d+)[a-z]{2} place.*?received \$(\d+\.?\d*)',
            raw, re.IGNORECASE
        )
        if m:
            result['place'] = int(m.group(1))
            result['prize'] = float(m.group(2))
        else:
            # Sem prêmio (eliminado antes do dinheiro)
            m = re.search(
                re.escape(hero) + r'.*?finished.*?(\d+)[a-z]{2} place',
                raw, re.IGNORECASE
            )
            if m:
                result['place'] = int(m.group(1))
                result['prize'] = 0.0

    if result['buy_in'] and result['prize'] is not None:
        result['profit'] = round(result['prize'] - result['buy_in'], 2)

    return result


def _extract_date(raw: str) -> str | None:
    """
    Extrai a data do jogo do hand history.
    PokerStars: '2025/07/22 10:10:49 ET' → '2025-07-22'
    Usa a primeira mão do arquivo (mais antiga) para representar quando o torneio começou.
    """
    import re
    # Data + hora completa: 2025/07/22 10:10:49
    m = re.search(r'(\d{4})/(\d{2})/(\d{2})\s+\d{2}:\d{2}:\d{2}', raw)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    # Fallback: só data
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
    from leaklab.llm_explainer import generate_study_plan

    days = int(request.args.get('days', 90))

    # Buscar dados do banco
    leaks    = get_leak_summary(g.user_id, days)
    evolution = get_evolution_metrics(g.user_id, days)
    icm      = get_icm_performance(g.user_id, days)

    if not leaks and not evolution:
        return jsonify({'error': 'Sem dados suficientes — importe torneios primeiro'}), 400

    # Buscar nome do hero
    from database.repositories import get_tournaments
    tourns = get_tournaments(g.user_id, limit=1)
    hero   = tourns[0]['hero'] if tourns else 'Jogador'

    plan = generate_study_plan(leaks, evolution, icm, hero=hero, user_id=g.user_id)
    return jsonify(plan)


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

    # Buscar decisões desta mão do banco para marcar erros
    decisions_db = get_decisions(t['id'])
    hand_decisions = [d for d in decisions_db if str(d.get('hand_id')) == str(hand_id)]

    # Construir replay data
    replay = _build_replay_data(target, hand_decisions, t.get('hero', target.hero))
    return jsonify(replay)


def _build_replay_data(hand, decisions_db, hero_override=None):
    """Constrói a timeline completa de replay a partir de uma ParsedHand."""
    import re as _re
    from leaklab.hand_state_builder import _normalize_action

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
            timeline.append(snap({'type': 'street', 'desc': street.upper()}))

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
            'type':         'action',
            'player':       action.player,
            'seat':         pseat,
            'action':       _normalize_action(action.action),
            'amount':       amt,
            'is_hero':      action.player == hero,
            'is_error':     decision is not None,
            'error_label':  decision.get('label')       if decision else None,
            'error_score':  round(float(decision.get('score', 0)), 3) if decision else None,
            'best_action':  decision.get('best_action')  if decision else None,
            'desc':         f"{action.player}: {_normalize_action(action.action)}"
                              + (f' {int(amt)}' if amt else ''),
            **err_extra,
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


@app.errorhandler(413)
def too_large(_): return jsonify({'error': 'Arquivo muito grande (limite: 5MB)'}), 413

@app.errorhandler(405)
def method_not_allowed(_): return jsonify({'error': 'Método não permitido'}), 405

@app.errorhandler(404)
def not_found(_): return jsonify({'error': 'Rota não encontrada'}), 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)
