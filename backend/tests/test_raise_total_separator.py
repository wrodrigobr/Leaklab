"""
Regressão do bug "RAISE de 0bb" no Replayer (reportado em prod 2026-07-25, CoinPoker).

O /replay reparseava a linha crua com `raises \\d+ to (\\d+)`. O `\\d+` PARA na vírgula do
separador de milhar, então em "raises 798 to 1,098" (CoinPoker/GGPoker) ele capturava **"1"**:
o assento mostrava RAISE com 1 ficha (0,003 BB → exibido "0 BB") e o pote não recebia o valor.

A leitura da linha crua passou a viver no parser (raise_total_from_raw), tolerante a separador
de milhar (vírgula/espaço), decimais e à variante sem incremento ("raises to Y").
"""
import sys, os, traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import raise_total_from_raw


def test_coinpoker_thousand_separator():
    """O caso EXATO do bug: total com vírgula de milhar não pode truncar em '1'."""
    assert raise_total_from_raw("a7da4b75: raises 798 to 1,098") == 1098.0
    assert raise_total_from_raw("419d6253: raises 440 to 1,280") == 1280.0
    print("OK  test_coinpoker_thousand_separator")


def test_gg_thousand_separator_returns_total_not_increment():
    """GGPoker: antes o regex não casava e caía no incremento (1109) em vez do total (2218)."""
    assert raise_total_from_raw("Villain: raises 1,109 to 2,218") == 2218.0
    print("OK  test_gg_thousand_separator_returns_total_not_increment")


def test_pokerstars_and_acr_unchanged():
    """Formatos que já funcionavam seguem idênticos (sem regressão)."""
    assert raise_total_from_raw("Villain: raises 300 to 400") == 400.0
    assert raise_total_from_raw("1IrieMonn raises 4950.00 to 5700.00") == 5700.0   # ACR decimais
    print("OK  test_pokerstars_and_acr_unchanged")


def test_allin_and_space_separator_and_no_increment():
    assert raise_total_from_raw("X: raises 500 to 32,500 and is all-in") == 32500.0
    assert raise_total_from_raw("ibslower raises 7218.00 to 7218.00 and is all-in") == 7218.0
    assert raise_total_from_raw("Villain: raises 1 500 to 3 000") == 3000.0   # milhar com ESPAÇO
    assert raise_total_from_raw("Villain: raises to 400") == 400.0            # sem incremento
    print("OK  test_allin_and_space_separator_and_no_increment")


def test_non_raise_returns_none():
    """Linha que não é 'raises ... to ...' devolve None (o caller usa o amount normal)."""
    assert raise_total_from_raw("Villain: calls 300") is None
    assert raise_total_from_raw("Villain: bets 500") is None
    assert raise_total_from_raw("") is None
    assert raise_total_from_raw(None) is None
    print("OK  test_non_raise_returns_none")


def test_replay_renders_bet_in_bb_not_zero():
    """Ponta a ponta: o total do raise, convertido pra BB, não pode arredondar pra 0.
    Com o bug, 1 ficha / bb 300 = 0,003 BB → a mesa exibia '0 BB'."""
    bb = 300.0
    total = raise_total_from_raw("a7da4b75: raises 798 to 1,098")
    assert total is not None
    assert round(total / bb, 1) == 3.7, round(total / bb, 1)   # 3,66 BB — visível na mesa
    print("OK  test_replay_renders_bet_in_bb_not_zero")


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
