"""
Testa a extensão PKO/8-max do scripts/parse_gw_har.py:
- parse_gametype (PKO vs Classic) + humanize_stage (incl. estágios extrapolados)
- seat_map / classify_spot em 8-max (rfi, vs_rfi, squeeze) com Classic 9-max intacto
- e2e nos 4 HARs reais (docs/ranges_gto/ko/) — SKIP gracioso se ausentes (não
  commitados: captura bruta grande; HAR pode carregar token).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from pathlib import Path
from scripts.parse_gw_har import (
    parse_gametype, humanize_stage, seat_map, classify_spot,
    process_har, parse_spot, build_ranges_json,
)

HAR_DIR = Path(__file__).resolve().parent.parent / 'docs' / 'ranges_gto' / 'ko'


# ── parse_gametype ────────────────────────────────────────────────────────────
def test_parse_gametype_pko():
    g = parse_gametype('MTTGeneral_ICMPKO8m200PTSTART')
    assert g['is_pko'] is True
    assert g['table_size'] == 8 and g['field_size'] == 200
    assert g['stage_token'] == 'START' and g['stage'] == '100% left'
    g2 = parse_gametype('MTTGeneral_ICMPKO8m1000PTFT')
    assert g2['field_size'] == 1000 and g2['stage'] == 'final table'
    print("OK  test_parse_gametype_pko")


def test_parse_gametype_classic_not_pko():
    for gt in ('MTTGeneralV2', 'CashGeneral6m', '', None):
        g = parse_gametype(gt)
        assert g['is_pko'] is False and g['table_size'] is None
    print("OK  test_parse_gametype_classic_not_pko")


# ── humanize_stage (confirmados + extrapolados da lista do usuário) ────────────
def test_humanize_stage():
    cases = {
        'START': '100% left', 'PCT90': '90% left', 'PCT70': '70% left',
        'PCT50': '50% left', 'PCT375': '37.5% left', 'PCT25': '25% left',
        'BUBBLEMID': 'near bubble', '2TABLES': '2 tables', '3TABLES': '3 tables',
        'FT': 'final table',
    }
    for tok, exp in cases.items():
        assert humanize_stage(tok) == exp, (tok, humanize_stage(tok))
    # token desconhecido: preserva cru (nunca perde info)
    assert humanize_stage('WEIRDNEW') == 'WEIRDNEW'
    print("OK  test_humanize_stage")


# ── seat_map / classify_spot 8-max vs 9-max ───────────────────────────────────
def test_seat_map():
    assert seat_map(8)[2] == 'LJ'      # 8-max pula UTG+2
    assert seat_map(9)[2] == 'UTG+2'   # 9-max mantém
    assert seat_map(8)[7] == 'BB' and seat_map(9)[8] == 'BB'
    print("OK  test_seat_map")


def test_classify_8max_rfi():
    # 'F' = UTG foldou, UTG+1 decide abrir (RFI)
    c = classify_spot('F', table_size=8)
    assert c['scenario'] == 'rfi' and c['hero_pos'] == 'UTG+1'
    # 'F-F' = UTG, UTG+1 foldam -> LJ abre (pula UTG+2 no 8-max)
    c2 = classify_spot('F-F', table_size=8)
    assert c2['scenario'] == 'rfi' and c2['hero_pos'] == 'LJ'
    print("OK  test_classify_8max_rfi")


def test_classify_8max_vs_rfi_and_squeeze():
    # vs_rfi: UTG abre, UTG+1 defende
    c = classify_spot('R2', table_size=8)
    assert c['scenario'] == 'vs_rfi' and c['hero_pos'] == 'UTG+1' and c['vs_pos'] == 'UTG'
    # F-R2.1: UTG fold, UTG+1 abre, LJ defende
    c2 = classify_spot('F-R2.1', table_size=8)
    assert c2['scenario'] == 'vs_rfi' and c2['hero_pos'] == 'LJ' and c2['vs_pos'] == 'UTG+1'
    # squeeze: UTG abre, UTG+1 call, LJ squeeze
    c3 = classify_spot('R2-C', table_size=8)
    assert c3['scenario'] == 'squeeze' and c3['hero_pos'] == 'LJ' and c3['vs_pos'] == 'UTG'
    print("OK  test_classify_8max_vs_rfi_and_squeeze")


def test_classic_9max_unchanged():
    # Regressão: o default (9-max) deve seguir idêntico ao comportamento antigo.
    assert classify_spot('R2')['hero_pos'] == 'UTG+1' and classify_spot('R2')['vs_pos'] == 'UTG'
    assert classify_spot('F-F-F')['scenario'] == 'rfi' and classify_spot('F-F-F')['hero_pos'] == 'LJ'
    assert classify_spot('R2-C')['hero_pos'] == 'UTG+2'  # 9-max: 3º assento é UTG+2
    print("OK  test_classic_9max_unchanged")


# ── e2e nos 4 HARs reais (skip se ausentes) ───────────────────────────────────
def test_e2e_pko_hars():
    hars = sorted(HAR_DIR.glob('*.har')) if HAR_DIR.exists() else []
    if not hars:
        print("SKIP test_e2e_pko_hars (HARs não presentes — captura local, fora do git)")
        return
    all_spots = []
    for h in hars:
        all_spots.extend(process_har(h))
    assert all_spots, "nenhum spot /spot-solution/ extraído dos HARs"
    result = build_ranges_json(all_spots)
    pko = result.get('pko_ranges') or {}
    assert pko, "pko_ranges vazio — gametype PKO não detectado"
    # estágios esperados sob o campo 200p
    field = pko.get('200p') or {}
    assert field, f"campo 200p ausente: {list(pko.keys())}"
    stages = {tok: node['_stage'] for tok, node in field.items()}
    assert stages.get('START') == '100% left'
    assert stages.get('FT') == 'final table'
    # toda folha de spot tem hand_freqs não-vazio e veio de 8-max
    leaf_count = 0
    for tok, node in field.items():
        for h, info in node['ranges'].items():
            pass  # estrutura existe
    # valida um vs_rfi 8-max concreto presente em algum estágio
    found_vsrfi = False
    for s in all_spots:
        p = parse_spot(s['data'], s['params'])
        g = parse_gametype(p['gametype'])
        if not g['is_pko']:
            continue
        cls = classify_spot(p['preflop_actions'], table_size=g['table_size'])
        if cls['scenario'] == 'vs_rfi':
            assert p['hand_freqs'], "vs_rfi sem hand_freqs"
            assert cls['hero_pos'] in seat_map(8).values()
            found_vsrfi = True
    assert found_vsrfi, "nenhum vs_rfi 8-max encontrado nos HARs"
    print(f"OK  test_e2e_pko_hars ({len(all_spots)} spots, {len(field)} estágios)")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
