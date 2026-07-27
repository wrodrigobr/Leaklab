"""
Prévia do trilho lento: o que a validação diria HOJE sobre cada leak treinado.

Responde "os torneios que acabei de importar já mostram melhora?" antes de a tela mostrar.

SOMENTE LEITURA — de propósito. O `get_training_proof` do produto tem um efeito colateral
legítimo: quando a regressão é comprovada, ele REABRE o leak e move o baseline. Uma prévia que
mexesse no seu plano de estudo por ter sido consultada seria armadilha, então esta sonda não passa
por ele: lê os mesmos dados e chama a MESMA função de veredito (`validation.validate_leak`).
Reusar a matemática é o ponto — uma query própria criaria uma segunda definição de "melhorou",
que é exatamente a classe de bug que mais custou tempo neste projeto.

Também não cria baseline. Categoria sem baseline gravado aparece como "sem baseline" em vez de
ganhar um agora (o que congelaria a linha no momento errado, DEPOIS do treino).

Uso:
    cd ~/app && docker compose exec web python -m scripts.diag_validacao SEU_EMAIL
    cd ~/app && docker compose exec web python -m scripts.diag_validacao --user-id 3
"""
import sys, os, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import (
    _adapt, _fetchone, _fetchall,
    _category_adherence_filter, _category_error_counts, _user_global_error_rate,
)
from leaklab.validation import (
    validate_leak, VALIDATION_MIN_N, BASELINE_MIN_N,
    V_MELHOROU, V_PIOROU, V_SEM_MUDANCA, V_SEM_AMOSTRA,
)

_MARCA = {V_MELHOROU: '✔', V_PIOROU: '✖', V_SEM_MUDANCA: '=', V_SEM_AMOSTRA: '·'}


def _resolver_usuario(conn, alvo):
    if str(alvo).isdigit():
        r = _fetchone(conn, _adapt("SELECT id, username, email FROM users WHERE id = ?"), (int(alvo),))
    else:
        r = _fetchone(conn, _adapt("SELECT id, username, email FROM users WHERE lower(email) = ?"),
                      (str(alvo).lower(),))
    return dict(r) if r else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('alvo', nargs='?', help='email do usuário')
    ap.add_argument('--user-id', dest='uid')
    args = ap.parse_args()
    alvo = args.uid or args.alvo
    if not alvo:
        ap.error('informe o email ou --user-id')

    conn = get_conn()
    try:
        u = _resolver_usuario(conn, alvo)
        if not u:
            print(f"usuário não encontrado: {alvo}")
            return
        print(f"usuário: {u['username']} (id={u['id']})")
        print(f"mínimos: baseline ≥ {BASELINE_MIN_N} decisões · depois ≥ {VALIDATION_MIN_N}\n")

        global_rate = _user_global_error_rate(conn, u['id'])
        print(f"taxa de erro global (âncora do shrinkage): {global_rate * 100:.1f}%\n")

        skills = _fetchall(conn, _adapt(
            "SELECT category_key FROM training_skill_progress WHERE user_id=? ORDER BY category_key"),
            (u['id'],))
        if not skills:
            print("nenhuma categoria treinada ainda.")
            return

        vistos = 0
        for s in skills:
            key = s['category_key']
            if not _category_adherence_filter(key):
                continue      # postflop / não-mapeável: fora do trilho lento
            pr = _fetchone(conn, _adapt(
                "SELECT baseline_at, baseline_n FROM training_proof "
                "WHERE user_id=? AND category_key=?"), (u['id'], key))
            if not pr or int(pr['baseline_n'] or 0) <= 0:
                print(f"  ·  {key:34s} sem baseline gravado (treine para congelar o 'antes')")
                continue

            antes  = _category_error_counts(conn, u['id'], key, before=pr['baseline_at'])
            depois = _category_error_counts(conn, u['id'], key, after=pr['baseline_at'])
            if not antes or not depois:
                continue
            vistos += 1
            v = validate_leak(antes[0], antes[1], depois[0], depois[1], global_rate)

            print(f"  {_MARCA.get(v['veredito'], '?')}  {key:34s} {v['label']}")
            print(f"       antes : {v['taxa_antes']}%  ({antes[0]}/{antes[1]} decisões)"
                  + (f"   → ajustado {v['taxa_antes_ajustada']}%" if 'taxa_antes_ajustada' in v else ''))
            print(f"       depois: {v['taxa_depois']}%  ({depois[0]}/{depois[1]} decisões)")
            if 'ic_diferenca' in v:
                lo, hi = v['ic_diferenca']
                print(f"       IC 95% da queda: [{lo}, {hi}] pontos"
                      f"   {'(não cruza zero)' if lo > 0 or hi < 0 else '(cruza zero → indistinguível de ruído)'}")
            if v.get('faltam'):
                print(f"       faltam {v['faltam']} decisões com gabarito para abrir o veredito")
            print()

        if not vistos:
            print("nenhuma categoria com baseline + amostra para avaliar ainda.")
        print("(somente leitura — nada foi alterado; o leak NÃO é reaberto por esta consulta)")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
