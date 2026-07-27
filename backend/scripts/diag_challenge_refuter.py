"""Sonda de calibragem do voto adversarial do Desafio do Dia.

O problema que ela resolve: quando o refutador para de derrubar candidatos, não dá pra saber se
ele está BEM CALIBRADO ou INERTE (respondendo "não refuta" para tudo). O log só mostra o que ele
derruba — silêncio é ambíguo.

Aqui a resposta é medida, não inferida: submetemos spots com gabarito CONHECIDO e contamos os
dois erros que importam.

  · ISCAS (spots malformados de propósito) → ele DEVE refutar. Se passar, está inerte.
  · CONTROLES (spots legítimos, inclusive mistos e contraintuitivos) → ele NÃO deve refutar.
    Se derrubar, está agressivo e vai varrer a faixa difícil.

Custa REFUTE_VOTES chamadas de LLM por caso (padrão 3). Com 6 casos, ~18 chamadas de Haiku.

Uso:
    cd ~/app && docker compose exec web python -m scripts.diag_challenge_refuter
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass

from leaklab.daily_challenge import verify_challenge, REFUTE_VOTES


def _spot(**kw):
    base = {'scenario': 'vs_rfi', 'position': 'BB', 'vs_position': 'CO', 'stack_bb': 30,
            'hand': 'K8s', 'options': ['fold', 'call', 'raise']}
    base.update(kw)
    return base


def _ctx(strategy, best):
    return {'gto_strategy': [{'action': a, 'freq': f} for a, f in strategy], 'best_action': best}


# (nome, spot, ctx, resposta, deve_refutar)
CASOS = [
    # ── ISCAS: têm que ser derrubadas ──
    ("isca: ação fora do menu",
     _spot(options=['fold', 'call']), _ctx([('raise', 0.9), ('fold', 0.1)], 'raise'),
     'raise', True),
    ("isca: stack impossível",
     _spot(stack_bb=0.2), _ctx([('call', 0.8), ('fold', 0.2)], 'call'),
     'call', True),
    ("isca: posições incoerentes (herói e vilão no mesmo assento)",
     _spot(position='BB', vs_position='BB'), _ctx([('call', 0.7), ('fold', 0.3)], 'call'),
     'call', True),

    # ── CONTROLES: têm que passar ──
    ("controle: spot MISTO legítimo (54/46)",
     _spot(stack_bb=12, hand='AQs', scenario='vs_3bet', position='UTG', vs_position='CO',
           options=['fold', 'call', 'allin']),
     _ctx([('fold', 0.54), ('allin', 0.46)], 'fold'), 'fold', False),
    ("controle: contraintuitivo (mão bonita que folda)",
     _spot(stack_bb=50, hand='KQo', scenario='vs_3bet', position='UTG', vs_position='BTN',
           options=['fold', 'call', 'raise']),
     _ctx([('fold', 0.82), ('call', 0.18)], 'fold'), 'fold', False),
    ("controle: padrão claro",
     _spot(stack_bb=30, hand='AA', scenario='rfi', position='UTG', vs_position='',
           options=['fold', 'raise']),
     _ctx([('raise', 1.0)], 'raise'), 'raise', False),
]


def main():
    print(f"Sonda do refutador — {REFUTE_VOTES} peritos por caso, {len(CASOS)} casos.\n")
    falsos_neg = falsos_pos = indisp = 0
    for nome, spot, ctx, resp, deve in CASOS:
        r = verify_challenge(spot, ctx, answer=resp)
        v = r['veredito']
        if v == 'indisponivel':
            indisp += 1
            print(f"  ?  {nome}\n     LLM indisponível — sem veredito.")
            continue
        refutou = (v == 'refutado')
        ok = (refutou == deve)
        marca = '✔' if ok else '✖'
        if not ok:
            if deve:
                falsos_neg += 1
            else:
                falsos_pos += 1
        print(f"  {marca}  {nome}\n     esperado={'refutar' if deve else 'passar'} "
              f"obtido={v} ({r['refutacoes']}/{r['votos']} peritos)")
        if r['motivos']:
            print(f"     motivo: {r['motivos'][0][:150]}")

    print("\n" + "=" * 70)
    if indisp:
        print(f"⚠ {indisp} caso(s) sem LLM — rode onde a ANTHROPIC_API_KEY existe.")
    print(f"falsos NEGATIVOS (deixou passar isca): {falsos_neg}   ← alto = refutador INERTE")
    print(f"falsos POSITIVOS (derrubou spot bom): {falsos_pos}   ← alto = vai varrer a faixa difícil")
    if not indisp and falsos_neg == 0 and falsos_pos == 0:
        print("\n✔ calibrado: pega o malformado e deixa passar o difícil.")
    elif falsos_neg and not falsos_pos:
        print("\n→ frouxo demais: endureça a lista de motivos válidos em `_refute_prompt`.")
    elif falsos_pos and not falsos_neg:
        print("\n→ agressivo demais: reforce que misto/contraintuitivo NÃO é motivo.")


if __name__ == '__main__':
    main()
