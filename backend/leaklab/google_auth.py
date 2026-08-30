# -*- coding: utf-8 -*-
"""Login com Google: o token do botão vira a NOSSA sessão de sempre.

── Por que existe (30/08) ───────────────────────────────────────────────────────────────────

O gargalo do funil é ANTES do produto (28% dos cadastrados importam), e uma perda documentada
foi a fricção do cadastro — as 7 contas presas na verificação de e-mail quando o DNS mandava o
código pro spam. O Google elimina senha E verificação num toque: o e-mail já chega verificado.

── As três regras que evitam dor depois ─────────────────────────────────────────────────────

1. **Vínculo por e-mail verificado.** Conta existente com o mesmo e-mail? O Google entra NELA
   (grava o `google_sub`), nunca cria duplicata. A senha antiga continua valendo.
2. **Username gerado do prefixo do e-mail** (com sufixo em colisão) — sem tela extra no meio
   do fluxo, que é onde se perde gente. Renomeia no perfil depois.
3. **O Google só autentica; a sessão é NOSSA.** Verificado o token, emitimos o JWT de sempre
   (`generate_token`). Nada muda em rotas, `LEAKLAB_SECRET` ou permissões.

O verificador fica numa função própria (`_verificar_token_google`) para os testes poderem
substituí-lo: teste que depende do Google de verdade não roda em CI.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
from typing import Optional

_log = logging.getLogger(__name__)


def _verificar_token_google(credential: str, client_id: str) -> dict:
    """Valida o ID token contra as chaves públicas do Google e o NOSSO client_id.
    Levanta ValueError em token inválido. Substituível em teste."""
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token as g_id_token
    try:
        return g_id_token.verify_oauth2_token(credential, g_requests.Request(), client_id)
    except Exception as e:                                     # noqa: BLE001
        raise ValueError('token do Google invalido: %s' % e) from e


def _username_do_email(email: str) -> str:
    """Prefixo do e-mail saneado; sufixo numérico em colisão. Nunca falha por nome."""
    from database.repositories import get_user_by_username
    base = re.sub(r'[^a-z0-9_]', '', (email.split('@', 1)[0] or 'player').lower())[:20] or 'player'
    candidato = base
    n = 1
    while get_user_by_username(candidato):
        n += 1
        candidato = f'{base}{n}'
        if n > 500:                                            # paranoia; nunca deve acontecer
            candidato = f'{base}_{secrets.token_hex(3)}'
            break
    return candidato


def entrar_com_google(credential: str, ref: Optional[str] = None) -> dict:
    """Autentica (ou cria) o usuário a partir do ID token do Google.

    Devolve o dict do usuário (id, username, role) + `criado`/`vinculado` para telemetria.
    Levanta ValueError com mensagem segura em qualquer recusa.
    """
    from database.repositories import (create_user, get_coach_by_invite_key,
                                       get_user_by_email, get_user_by_google_sub,
                                       vincular_google_sub)

    client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    if not client_id:
        raise ValueError('login com Google indisponivel')

    claims = _verificar_token_google(credential, client_id)
    sub = str(claims.get('sub') or '')
    email = str(claims.get('email') or '').strip().lower()
    if not sub or not email:
        raise ValueError('token do Google sem identidade')
    # e-mail nao verificado NO GOOGLE e raro e suspeito — e derruba a regra 1 (vincular por
    # e-mail so e seguro porque o Google atesta a posse).
    if not claims.get('email_verified'):
        raise ValueError('e-mail do Google nao verificado')

    # 1) ja vinculado → login
    u = get_user_by_google_sub(sub)
    if u:
        return {**u, 'criado': False, 'vinculado': False}

    # 2) conta existente com o e-mail → VINCULA (nunca duplica)
    u = get_user_by_email(email)
    if u:
        vincular_google_sub(u['id'], sub)
        return {**u, 'criado': False, 'vinculado': True}

    # 3) conta nova — replica o caminho do /auth/register para o ref de coach
    coach_id = referral_coach_id = link_status = invited_by_key = None
    ref = (ref or '').strip().upper()
    if ref:
        _coach = get_coach_by_invite_key(ref)
        if _coach:
            coach_id = referral_coach_id = _coach['id']
            link_status = 'pending'
            invited_by_key = ref
    username = _username_do_email(email)
    # senha aleatoria inutilizavel: a conta nasce só-Google; "esqueci a senha" cobre quem
    # quiser criar uma depois.
    user_id = create_user(username, email, secrets.token_urlsafe(24),
                          coach_id=coach_id, referral_coach_id=referral_coach_id,
                          link_status=link_status, invited_by_key=invited_by_key,
                          acquisition_source='google', email_verified=1)
    vincular_google_sub(user_id, sub)
    _log.info('google login: conta criada user_id=%s (ref=%s)', user_id, ref or '-')
    return {'id': user_id, 'username': username, 'role': 'player',
            'criado': True, 'vinculado': False}
