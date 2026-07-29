"""
dev_login.py — lista os usuários do banco LOCAL e define senha para entrar no ambiente de dev.

    python scripts/dev_login.py                      # lista quem existe
    python scripts/dev_login.py aluno@a.com          # define a senha padrão de dev
    python scripts/dev_login.py aluno@a.com senha123 # define a senha que você quiser

── A trava, e por que ela é a primeira coisa do arquivo ──────────────────────────────────────

Este script TROCA SENHA. Num banco de produção seria uma tomada de conta com um comando de uma
linha, e a chance de alguém rodá-lo no terminal errado não é hipotética: esta sessão inteira foi
feita alternando entre o repositório local e um `docker compose exec` no host de produção.

Por isso ele se recusa a rodar quando `is_production()` — a MESMA função que arma o fail-safe do
JWT. Uma fonte só para "estamos em produção?": duas versões dessa pergunta já deixaram o
bloqueio do JWT desarmado por meses, porque a estreita não reconhecia o ambiente real.

A trava é por AMBIENTE e não por flag de linha de comando, de propósito: flag se digita por
engano, ambiente não.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.auth import is_production

if is_production():
    print('RECUSADO: este script troca senha e o ambiente parece ser PRODUÇÃO.')
    print('Sinais encontrados:', ', '.join(
        k for k in ('RENDER', 'LEAKLAB_PROD', 'ENVIRONMENT', 'DATABASE_URL')
        if os.environ.get(k)) or '(nenhum, mas is_production() devolveu True)')
    sys.exit(2)

from database.schema import get_conn, SQLITE_PATH
from database.repositories import _fetchall, _adapt, _hash_password

_SENHA_PADRAO = 'dev12345'


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    conn = get_conn()
    try:
        print(f'banco: {SQLITE_PATH}\n')
        usuarios = _fetchall(conn, _adapt(
            'SELECT id, email, username, role, plan FROM users ORDER BY id'), ())
        if not usuarios:
            print('nenhum usuário no banco local. Cadastre um pela tela de registro.')
            return

        if not args:
            print(f'{"id":>3}  {"email":34s} {"usuário":16s} {"papel":8s} plano')
            for u in usuarios:
                d = dict(u)
                print(f'{d["id"]:>3}  {str(d.get("email"))[:34]:34s} '
                      f'{str(d.get("username"))[:16]:16s} {str(d.get("role")):8s} {d.get("plan")}')
            print(f'\nPara entrar: python scripts/dev_login.py <email> [senha]')
            print(f'(sem senha, usa "{_SENHA_PADRAO}")')
            return

        email = args[0]
        senha = args[1] if len(args) > 1 else _SENHA_PADRAO
        alvo = next((dict(u) for u in usuarios
                     if (dict(u).get('email') or '').lower() == email.lower()), None)
        if not alvo:
            print(f'{email} não existe neste banco. Rode sem argumentos para ver a lista.')
            sys.exit(1)

        conn.execute(_adapt('UPDATE users SET password_hash = ?, email_verified = 1 WHERE id = ?'),
                     (_hash_password(senha), alvo['id']))
        conn.commit()
        print(f'senha definida para {alvo["email"]} ({alvo["role"]}, plano {alvo.get("plan")})')
        print(f'\n  email: {alvo["email"]}')
        print(f'  senha: {senha}')
        # `email_verified` junto: sem isso o login cai na tela de verificação por código e o
        # ambiente de dev não tem e-mail configurado — trava o teste por um motivo lateral.
        print('\n(email_verified marcado, senão o login pediria o código de verificação)')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
