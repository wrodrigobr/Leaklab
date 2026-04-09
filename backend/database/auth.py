"""
auth.py — Autenticação JWT simples.
Tokens com expiração de 7 dias.
"""
from __future__ import annotations
import os
import jwt
import datetime
from functools import wraps
from flask import request, jsonify, g
from .repositories import get_user_by_id

SECRET_KEY = os.environ.get('GAPHUNTER_SECRET', 'dev-secret-change-in-production')
TOKEN_DAYS  = int(os.environ.get('TOKEN_DAYS', 7))


def generate_token(user_id: int, role: str) -> str:
    payload = {
        'user_id': user_id,
        'role':    role,
        'exp':     datetime.datetime.utcnow() + datetime.timedelta(days=TOKEN_DAYS),
        'iat':     datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f):
    """Decorator — protege endpoints que precisam de login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({'error': 'Token ausente'}), 401
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Token inválido ou expirado'}), 401
        user = get_user_by_id(payload['user_id'])
        if not user:
            return jsonify({'error': 'Usuário não encontrado'}), 401
        g.user    = user
        g.user_id = user['id']
        g.role    = user['role']
        return f(*args, **kwargs)
    return decorated


def require_coach(f):
    """Decorator — só coaches e admins."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({'error': 'Token ausente'}), 401
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Token inválido'}), 401
        if payload.get('role') not in ('coach', 'admin'):
            return jsonify({'error': 'Acesso restrito a coaches'}), 403
        user = get_user_by_id(payload['user_id'])
        g.user    = user
        g.user_id = user['id']
        g.role    = user['role']
        return f(*args, **kwargs)
    return decorated


def _extract_token() -> str | None:
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return request.args.get('token') or request.cookies.get('token')
