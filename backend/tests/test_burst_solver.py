# -*- coding: utf-8 -*-
"""test_burst_solver.py — a regra que decide criar/destruir server na Hetzner (gasta dinheiro).

Trava: sobe só acima do ALTO e abaixo do MAX; desce só abaixo do BAIXO e passada a vida
mínima (anti-flapping); no meio, mantém. A execução (API/docker) mora no script de host e não
se testa aqui; a DECISÃO, que é onde um bug custa produção destruída ou fatura infinita, sim.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.burst_solver import decidir

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {msg}")


# sobe: backlog alto e sem burst
check(decidir(500, 0).acao == 'subir', 'pending 500 sem burst → subir')
check(decidir(400, 0).acao == 'subir', 'exatamente no limiar ALTO → subir (>=)')
check(decidir(399, 0).acao == 'manter', 'um abaixo do ALTO → manter')
# teto: nunca passa de MAX_BURST
check(decidir(9999, 1).acao == 'manter', 'MAX_BURST atingido → manter mesmo com fila enorme')
# desce: fila drenou E vida mínima cumprida
check(decidir(10, 1, minutos_do_mais_novo=30).acao == 'descer', 'fila baixa + 30min → descer')
check(decidir(50, 1, minutos_do_mais_novo=30).acao == 'descer', 'exatamente no BAIXO → descer (<=)')
check(decidir(51, 1, minutos_do_mais_novo=30).acao == 'manter', 'um acima do BAIXO → manter')
# anti-flapping: recém-criado não desce
check(decidir(10, 1, minutos_do_mais_novo=5).acao == 'manter', 'burst de 5min não desce (anti-flapping)')
# sem burst e fila baixa: nada a fazer
check(decidir(0, 0).acao == 'manter', 'sem fila e sem burst → manter')
# zona morta entre BAIXO e ALTO com burst vivo: mantém (histerese)
check(decidir(200, 1, minutos_do_mais_novo=90).acao == 'manter', 'zona morta com burst → manter')

print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
sys.exit(1 if failed else 0)
