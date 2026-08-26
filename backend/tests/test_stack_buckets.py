"""
Os DOIS esquemas de stack bucket — e por que unificá-los seria um bug.

Estava no backlog como "unificar os 2 esquemas divergentes (gto_utils × preflop)". Investigando,
a divergência é NECESSÁRIA: cada esquema está preso a uma fonte de dados diferente.

  · `preflop_gto_ranges._DEFAULT_BUCKETS` → pontos discretos (10/14/17/20/30/40/50/75/100bb) que
    precisam casar EXATAMENTE com as chaves do JSON de ranges. Um bucket sem chave correspondente
    é um lookup que devolve nada, e o spot fica sem cobertura em silêncio.

  · `gto_utils.STACK_BUCKETS` → faixas largas (0-10/10-20/20-35/35-60/60-100bb) que compõem o
    HASH do nó do solver postflop. Refiná-las invalidaria os nós já solvados e multiplicaria o
    custo de solve sem ganho.

Forçar um único esquema quebraria um dos dois lados. Estes testes existem para que a próxima
pessoa que ler "unificar buckets" no backlog encontre aqui o motivo de não fazer — e para pegar
o dia em que o JSON ganhar uma profundidade nova e o código não acompanhar.
"""
import sys, os, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.gto_utils import stack_bucket, STACK_BUCKETS
from leaklab.preflop_gto_ranges import (_stack_bucket, _DEFAULT_BUCKETS, _BALDES_RASOS,
                                        _load)


def test_buckets_preflop_casam_com_as_chaves_do_json():
    """A invariante que importa: bucket sem dado = lookup vazio e spot sem cobertura, calado."""
    d = _load()
    chaves = set()

    def walk(o, prof=0):
        if prof > 3 or not isinstance(o, dict):
            return
        for k, v in o.items():
            if isinstance(k, str) and k.endswith('bb'):
                chaves.add(k)
            walk(v, prof + 1)

    walk(d)
    # Duas listas, de propósito. `_DEFAULT_BUCKETS` roteia TUDO; `_BALDES_RASOS` (3-7bb) roteia
    # só a seção RFI, que é a única que a carta importada cobre — se entrasse na primeira, as
    # seções ausentes passariam a apontar para um balde vazio. A invariante que importa continua
    # a mesma dos dois lados: bucket sem dado é lookup vazio e spot sem cobertura, calado.
    codigo = {b[0] for b in _DEFAULT_BUCKETS} | {b[0] for b in _BALDES_RASOS}
    assert not (codigo - chaves), f"bucket no código sem dado no JSON: {sorted(codigo - chaves)}"
    assert not (chaves - codigo), f"profundidade no JSON sem bucket: {sorted(chaves - codigo)}"
    rasos = {b[0] for b in _BALDES_RASOS}
    assert rasos.isdisjoint({b[0] for b in _DEFAULT_BUCKETS}), (
        f"a faixa rasa {sorted(rasos)} entrou nas DUAS listas: no roteamento geral ela leva "
        "vs_RFI/vs_3bet para um balde que não tem essas seções")
    print(f"OK  test_buckets_preflop_casam_com_as_chaves_do_json ({len(codigo)} profundidades)")


def test_preflop_cobre_toda_a_reta_sem_buraco():
    """Qualquer stack tem que cair em ALGUM bucket — inclusive os extremos."""
    for bb in (0.5, 1, 9.9, 12, 15.5, 18.5, 25, 35, 45, 62.5, 87.5, 100, 500):
        b = _stack_bucket(float(bb))
        assert b in {x[0] for x in _DEFAULT_BUCKETS}, (bb, b)
    print("OK  test_preflop_cobre_toda_a_reta_sem_buraco")


def test_postflop_cobre_toda_a_reta_sem_buraco():
    for bb in (0, 1, 9.9, 10, 19.9, 20, 34.9, 35, 59.9, 60, 100, 1000):
        b = stack_bucket(float(bb))
        assert b in {x[2] for x in STACK_BUCKETS}, (bb, b)
    print("OK  test_postflop_cobre_toda_a_reta_sem_buraco")


def test_os_dois_esquemas_sao_mesmo_diferentes():
    """Documenta a divergência: se algum dia alguém 'unificar', este teste cai e obriga a
    reler o docstring antes de quebrar um dos dois lookups."""
    preflop = {b[0] for b in _DEFAULT_BUCKETS}
    postflop = {b[2] for b in STACK_BUCKETS}
    assert preflop != postflop
    assert not (preflop & postflop), f"rótulos colidindo: {sorted(preflop & postflop)}"
    print(f"OK  test_os_dois_esquemas_sao_mesmo_diferentes "
          f"(preflop={len(preflop)} pontos, postflop={len(postflop)} faixas)")


def test_stack_curto_nao_cai_no_bucket_profundo():
    """Regressão do protocolo: 12bb tem que virar '10bb'/'14bb', nunca '100bb'. Um shove
    classificado como spot de 100bb vira crítica de sizing absurda."""
    assert _stack_bucket(12.0) in ('10bb', '14bb'), _stack_bucket(12.0)
    assert _stack_bucket(17.0) == '17bb'
    assert stack_bucket(12.0) == '10-20bb'
    print("OK  test_stack_curto_nao_cai_no_bucket_profundo")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
    raise SystemExit(1 if failed else 0)
