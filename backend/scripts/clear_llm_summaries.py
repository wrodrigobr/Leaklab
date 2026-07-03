"""Limpa o resumo de IA salvo (tournaments.llm_summary) para forçar a REGERAÇÃO com o
prompt novo (o antigo invertia o sentido das métricas). O resumo é regerado no próximo
acesso ao torneio (consome 1 análise de IA por torneio regerado).

Uso:
  python -m scripts.clear_llm_summaries --tid 4012503894      # por tournament_id (o do jogo)
  python -m scripts.clear_llm_summaries --user 13             # todos os torneios de um usuário
  python -m scripts.clear_llm_summaries --all                 # TODOS (cuidado: regera tudo, custa IA)

Sem argumento, não faz nada (evita limpar tudo por engano).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn, USE_POSTGRES

_args = sys.argv[1:]


def _val(flag):
    return _args[_args.index(flag) + 1] if flag in _args and _args.index(flag) + 1 < len(_args) else None


def main():
    tid  = _val('--tid')
    user = _val('--user')
    do_all = '--all' in _args
    if not (tid or user or do_all):
        print(__doc__)
        return

    conn = get_conn()
    ph = '%s' if USE_POSTGRES else '?'
    if tid:
        where, params = f"tournament_id = {ph}", (tid,)
    elif user:
        where, params = f"user_id = {ph}", (int(user),)
    else:
        where, params = "1=1", ()

    cur = conn.execute(
        f"UPDATE tournaments SET llm_summary = NULL WHERE llm_summary IS NOT NULL AND {where}",
        params,
    )
    conn.commit()
    n = getattr(cur, 'rowcount', None)
    conn.close()
    print(f"Resumos limpos: {n if n is not None else '(desconhecido)'}. "
          f"Serão regerados (com o prompt corrigido) no próximo acesso a cada torneio.")


if __name__ == '__main__':
    main()
