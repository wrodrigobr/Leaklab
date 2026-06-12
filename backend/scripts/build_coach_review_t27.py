# -*- coding: utf-8 -*-
"""Relatório de validação: review do coach (YouTube) × GrindLab — torneio #27 (Big $22).

Cruza a transcrição do review profissional com as decisões avaliadas pelo nosso
engine/GTO Solver no mesmo torneio (tournaments.id=388, tournament_id='27').
Saída: backend/docs/coach_review_t27.html (standalone, dark, marca GrindLab).

Associação transcrição↔mão: posicional (o vídeo cobre as mãos em ordem) +
âncoras de cartas/board. Entradas curadas manualmente — só associações de alta
confiança entram; o resto é contabilizado como "sem comentário substantivo".
"""
import io, json, os, sqlite3
from collections import Counter

DB   = os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db')
OUT  = os.path.join(os.path.dirname(__file__), '..', 'docs', 'coach_review_t27.html')
TID  = 388

# ── Entradas curadas: associação transcrição ↔ mão ↔ veredito ─────────────────
# status: match | parcial | diverge | bug
# fonte_certa: quem a análise final favorece — 'ambos' | 'sistema' | 'coach' | 'investigar'
E = [
 dict(h=1, cards="AJo", pos="UTG", spot="Call do 3-bet preflop",
      quote="“Tribet alto. Pode largar. Você acompanhou… eu acho um pouco agressivo.”",
      coach="FOLD vs 3-bet", system="FOLD (call = gto_critical)",
      ind="facing 8.6bb · 166bb deep", status="match", fonte="ambos",
      why="Coach e GTO Solver concordam: AJo não defende 3-bet grande OOP-ish a 166bb. Hero errou."),
 dict(h=2, cards="75o", pos="BB", spot="Defesa de BB vs min-raise",
      quote="“Segunda mão, 57, fold.” (sem crítica)",
      coach="FOLD ok", system="CALL (fold = gto_critical, EV −0.04bb)",
      ind="facing 2.2bb · EV loss 0.04bb", status="diverge", fonte="sistema",
      why="Por GTO, 75o defende vs min-raise com essas odds — mas o EV perdido é ~0.04bb. Estamos certos na DIREÇÃO, porém o selo 'critical' é desproporcional ao custo. → calibrar severidade pelo EV."),
 dict(h=3, cards="AQo", pos="BTN", spot="3-bet vs open",
      quote="“Aqui você pode dar um tribet para 6,5… 7,5 tá bom.”",
      coach="3-BET", system="CALL preferido (3-bet = standard, score 0.08)",
      ind="vs open 2.2bb · 116bb", status="parcial", fonte="ambos",
      why="Spot de mix real: solver mistura call/3-bet com AQo no BTN. As duas indicações são jogáveis; nenhuma é erro."),
 dict(h=4, cards="A6s", pos="BTN", spot="Flat vs open + linha pós-flop",
      quote="“Não gosto. Eu simplesmente foldaria… eventualmente tribet light.”",
      coach="FOLD (ou 3-bet light)", system="CALL (gto_correct)",
      ind="facing 2.0bb · 195bb deep", status="diverge", fonte="sistema",
      why="A6s no BTN vs open está no range de defesa por chart GTO (mix call/3-bet; fold é a pior das três). A objeção do coach é exploit ('ele não disputa bem') — válida como ajuste, não como baseline. No river ambos criticaram a aposta do hero (match)."),
 dict(h=5, cards="A2s", pos="BB", spot="Call no flop com A-high vs bet + caller",
      quote="“Não me parece que você tá bem não.”",
      coach="FOLD", system="FOLD (call = clear_mistake, EV −0.79bb)",
      ind="facing 4bb em pote 13bb · EV −0.79bb", status="match", fonte="ambos",
      why="Concordância total com EV mensurado: A-high multiway sem equity não continua."),
 dict(h=7, cards="AQo", pos="UTG+1", spot="C-bet multiway + barrel no turn",
      quote="“Pode dar mesa. Tá muita gente na mão… Você deu CBET ainda? Não me parece bom… não aconselho.”",
      coach="CHECK (não c-bet multiway)", system="CHECK (turn barrel = gto_critical, EV −0.82bb)",
      ind="3 jogadores · EV turn −0.82bb", status="match", fonte="ambos",
      why="Match forte nas duas streets: c-bet sem equity em campo multiway é punido pelos dois."),
 dict(h=8, cards="ATo", pos="BB", spot="Iso-raise vs limper",
      quote="“O small completou e você fez 3,5. Justo, justo.”",
      coach="ISO-RAISE", system="CALL preferido (raise = marginal)",
      ind="pote limpado · sem cobertura GTO", status="diverge", fonte="coach",
      why="Iso de limper com ATo no BB é padrão. Nosso engine não tem range dedicada a potes LIMPADOS e caiu em heurística conservadora. → calibração: ranges de iso vs limp."),
 dict(h=10, cards="A8s", pos="CO", spot="Bluff-catch no river",
      quote="“Eu daria uma olhada com Ás alto por cinco blinds num pote de 30.”",
      coach="CALL (exploit vs recreativo)", system="FOLD (gto_correct)",
      ind="facing 5bb em pote 28bb · pot odds 15%", status="diverge", fonte="ambos",
      why="Pelo preço (15%), o call exploit do coach é defensável contra campo que blefa demais; pelo solver, A-high está abaixo do bluff-catching range. GTO × exploit documentado — não é erro de nenhum lado."),
 dict(h=12, cards="55", pos="CO", spot="Fold vs 3-bet (set-mine)",
      quote="“Você tem que pagar… 4 blinds tá barato, potencial de ganhar 80.”",
      coach="CALL (implied odds)", system="FOLD (gto_correct)",
      ind="facing 6bb · stacks 100bb", status="diverge", fonte="ambos",
      why="Matematicamente o set-mine pede ~15:1 implícitas — 100bb atrás chega perto, MAS exige realizar tudo. Solver folda 55 vs 3-bet nesse sizing; o call do coach é exploit contra quem paga demais pós-flop. Divergência legítima."),
 dict(h=13, cards="QQ", pos="BB", spot="3-bet por valor",
      quote="“Você tem que proteger a sua mão… tá correto aqui o tribet.”",
      coach="3-BET", system="3-BET (gto_correct)",
      ind="—", status="match", fonte="ambos", why="Trivial e unânime."),
 dict(h=15, cards="ATs", pos="HJ", spot="Fold vs squeeze",
      quote="“Tomou um squeeze para 10… você vai largar. Largou muito bem.”",
      coach="FOLD", system="RAISE?! (fold = clear_mistake 0.47)",
      ind="facing 9bb · sem cobertura GTO (squeeze pot)", status="bug", fonte="coach",
      why="O coach está certo: ATs folda vs squeeze a 90bb. Nossa indicação 'raise' veio da HEURÍSTICA (squeeze pots estão fora das ranges capturadas) e está agressiva demais. → calibração: gate de confiança quando não há cobertura GTO."),
 dict(h=16, cards="AQs", pos="UTG", spot="Call em board monotone + label inconsistente",
      quote="“Nesse tipo de board, eu largaria… 8-9-valete, [três do mesmo naipe].”",
      coach="FOLD", system="CALL (best=call) mas rotulado gto_critical EV −0.41",
      ind="board 8c Jc 9c · sem clube na mão", status="bug", fonte="investigar",
      why="Inconsistência interna nossa: a ação do hero COINCIDE com o best do solver e ainda assim recebeu selo crítico (EV hand-aware vs ação agregada se misturaram no rotulador). O mérito (call pequeno IP) é defensável vs coach; o LABEL é bug. No river, ambos aprovaram o overbet bluff (match)."),
 dict(h=19, cards="A9o", pos="BB", spot="Reshove vs open do SB",
      quote="“Eu já daria a win. 18 blinds [dele], A9 contra quem abre bastante… jogou bem.”",
      coach="JAM", system="CALL (shove = gto_critical, EV −0.29bb)",
      ind="hero 40bb · vilão ~18bb · EV −0.29bb", status="diverge", fonte="ambos",
      why="Com o STACK DO VILÃO (18bb) o jam funciona como reshove e o coach tem razão prática; nosso EV considera o stack efetivo e prefere call por 0.29bb. Margem pequena — ambos jogáveis."),
 dict(h=22, cards="A2o", pos="BB", spot="3-bet light + SHOVE com a sequência feita",
      quote="“Tribet light? Gosto… [turn 5: A-2-3-4-5] agora a gente fez a sequência… ele mandou, você dá o win. Perfeito.”",
      coach="3-bet light OK · shove TRIVIAL (wheel)", system="3-bet = clear_mistake · shove turn = FOLD?!",
      ind="board 4c 3h Jh 5c — hero A2 = WHEEL", status="bug", fonte="coach",
      why="ACHADO CRÍTICO: no turn o hero tem a sequência A-5 (nuts efetivo) e nosso sistema indicou FOLD — leitura de força de mão errada no nó (provável mismatch de nó/board no postflop). O shove é obviamente correto. → investigar detecção de straight no avaliador. No pré, tema recorrente: punimos 3-bet light de BB que o coach adora."),
 dict(h=25, cards="AQo", pos="BTN", spot="Raise no turn vs aposta",
      quote="“Não faz sentido o raise aqui… ou deixa ele blefar, ou aposta baixa no flop.”",
      coach="NÃO raise (call)", system="NÃO raise (fold; raise = clear_mistake EV −4.48bb)",
      ind="EV −4.48bb (maior erro do torneio)", status="match", fonte="ambos",
      why="Ambos condenam o raise — divergem só no plano B (coach: call; sistema: fold). O hero cortou os blefs do vilão exatamente como o coach descreveu."),
 dict(h=26, cards="AKs", pos="BB", spot="Shove river com A-high",
      quote="“Aqui você vai dar o win, tentar tirar ele da mão.”",
      coach="JAM (blef)", system="CHECK (shove = gto_critical)",
      ind="pote 23bb · vilão slow-play trinca", status="diverge", fonte="sistema",
      why="O resultado deu razão ao solver: vilão tinha trinca e não folda nada melhor. AK-high no river vira bluff-catcher; jam só tira mãos que já perdiam. Argumento de fold equity do coach não se sustenta contra range que chega ao river."),
 dict(h=28, cards="99", pos="UTG", spot="Bluff-catch river vs aposta de meio pote",
      quote="“Me parece que tá perdendo… pode foldar. Você deu call ainda.” (vilão tinha A7 — chegou)",
      coach="FOLD", system="CALL (gto_correct)",
      ind="facing 6.8bb em pote 17.8bb", status="diverge", fonte="sistema",
      why="O coach leu certo ESTA mão (vilão tinha valor), mas pelo preço (28%) 99 precisa defender parte das vezes ou vira alvo de blef. Resultado ≠ processo: o call é correto em frequência."),
 dict(h=31, cards="77", pos="BB", spot="Calls no turn e river vs triple barrel",
      quote="“Pode largar… difícil dar o call, hein? Você pagou… e acertou. Blef completo.”",
      coach="FOLD/FOLD", system="FOLD/FOLD (EV −1.94 / −1.73bb)",
      ind="EV turn −1.94bb · river −1.73bb", status="match", fonte="ambos",
      why="A vitrine de 'processo > resultado': hero pagou tudo e GANHOU de um blef — e mesmo assim coach E sistema marcam os dois calls como erro. Alinhamento perfeito com EV quantificado."),
 dict(h=32, cards="88", pos="BTN", spot="Fold no turn vs barrel",
      quote="“E agora você vai largar, né? Ok. Justo. Essa é a linha que eu usaria.”",
      coach="FOLD", system="CALL (fold = clear_mistake, EV −2.09bb)",
      ind="facing 5.8bb em pote 15bb · EV −2.09bb", status="diverge", fonte="sistema",
      why="Maior divergência quantificada a nosso favor: 88 em T-2-T-J é bluff-catcher com preço de 28%; o solve hand-aware mede 2.09bb deixados na mesa. O 'justo' do coach é overfold."),
 dict(h=33, cards="99", pos="CO", spot="Open-shove 62bb",
      quote="“Não manda win por cima não… tribet para seis, se ele der [all-in] você paga.”",
      coach="3-BET pequeno", system="CALL/3-bet (shove = small_mistake, EV −1.08bb)",
      ind="62bb efetivos · EV −1.08bb", status="match", fonte="ambos",
      why="Ambos contra o jam gigante — discordam apenas na alternativa (3-bet vs call). Convergência no que importa: não torrar 62bb pré com 99."),
 dict(h=35, cards="J9o", pos="BB", spot="Call no flop com par de J",
      quote="“Pegou o valete… check-call. [aprova a linha passiva]”",
      coach="CALL", system="FOLD?! (call = clear_mistake 0.64, sem GTO)",
      ind="facing 1.9bb em pote 3.5bb · heurística", status="bug", fonte="coach",
      why="Par de J em K-6-J por aposta de meio pote é continue trivial. Sem cobertura GTO o engine caiu em heurística overfold. Mesmo padrão do item ATs vs squeeze. → calibração da heurística postflop em potes pequenos."),
 dict(h=36, cards="JJ", pos="HJ", spot="Reshove vs all-in de 9bb",
      quote="“Aqui sim, eu vou isolar… parte valete me parece tá bem.”",
      coach="JAM", system="JAM (gto_correct)",
      ind="—", status="match", fonte="ambos", why="Unânime."),
 dict(h=37, cards="66", pos="HJ", spot="Limp pré + linha com trinca/full",
      quote="“Não dê limp… Você deu mesa com a trinca, não pode… [river] pode dar uma win nele.”",
      coach="RAISE pré · BET turn · RAISE river", system="RAISE pré ✓ · BET turn ✓ · river shove = FOLD?!",
      ind="board 5c As 4d 6c 4s — hero 66 = FULL HOUSE", status="bug", fonte="coach",
      why="SEGUNDO achado crítico de leitura de mão: no river o hero tem full house (66 + 44) e nosso nó indicou fold. Mesmo padrão do item A2 (wheel): avaliação hand-aware usando nó errado. Pré e turn batemos com o coach."),
 dict(h=45, cards="JTs", pos="SB", spot="Fold vs 4-bet shove 37bb",
      quote="“Tomou forbet… você vai ter que largar. Ok.”",
      coach="FOLD", system="CALL (fold = clear_mistake, EV −0.62bb)",
      ind="facing 37bb · pote 45.5bb", status="diverge", fonte="ambos",
      why="Pelo preço o call de JTs é levemente +EV vs range de shove largo; vs 4-bet apertado, fold. Depende 100% do read — divergência fina (0.62bb), ambos defensáveis."),
 dict(h=50, cards="22", pos="BB", spot="3-bet light vs SB",
      quote="“Eu vou dar o all-in no semiblef… o tribet com par baixo é o problema.”",
      coach="JAM (semibluff)", system="CALL (3-bet = clear_mistake)",
      ind="vilão 25bb abre 38% do SB", status="diverge", fonte="ambos",
      why="Três caminhos (hero 3-betou, coach jamaria, sistema pagaria). Vs SB de 38% de open, o jam do coach tem mérito exploit; o call do solver preserva equity barata. O 3-bet pequeno do hero era o pior dos três — nisso ambos concordam."),
 dict(h=51, cards="J8o", pos="BTN", spot="Open raise no BTN",
      quote="“Acho que valete-10 é o range… valete-8 acho que tá fora.”",
      coach="FOLD (fora do range)", system="RAISE (gto_correct?!)",
      ind="50bb · charts BTN", status="diverge", fonte="coach",
      why="J8o está FORA do RFI de BTN na maioria dos charts a 50bb (J8s sim, J8o não). Nossa range de BTN aceita largo demais aqui. → calibração: revisar fronteira do RFI BTN no preflop DB."),
 dict(h=54, cards="77", pos="BB", spot="Donk bet flop + bet river com mão média",
      quote="“Donk bet com mãos médias não é bom… você não ganha valor apostando par de 7 — check-call.”",
      coach="CHECK (2x)", system="CHECK (2x — donk = marginal, river bet = marginal)",
      ind="—", status="match", fonte="ambos",
      why="Match duplo na mesma mão: as duas linhas finas do hero reprovadas pelos dois avaliadores."),
 dict(h=57, cards="AKo", pos="UTG+1", spot="Call vs 3-bet (mix) + label inconsistente no turn",
      quote="“Agora você só deu call. Muito legal… o cara vai ter dificuldade na sua leitura.”",
      coach="CALL (mix) ótimo", system="RAISE preferido (call = small_mistake) · turn fold = best E clear_mistake (EV 8.14?!)",
      ind="turn: act=fold, best=fold, label=critical", status="bug", fonte="investigar",
      why="Dois pontos: (1) o call de AK vs 3-bet é mix legítimo — punimos um lado do mix; (2) no turn a ação do hero IGUALA o best e ainda levou clear_mistake com EV 8.14 — mesma inconsistência de rotulagem do item AQs (board monotone). Bug de labeling confirmado em 2 mãos."),
 dict(h=58, cards="A4o", pos="BB", spot="3-bet light",
      quote="“Foi pro tribet light. Gosto, gosto.”",
      coach="3-BET light", system="CALL (3-bet = clear_mistake 0.46)",
      ind="tema recorrente (A2o, 22, A4o)", status="diverge", fonte="ambos",
      why="TERCEIRA ocorrência do padrão: coach adora 3-bet light de blind, nosso sistema pune com 'critical'. GTO mixa essas mãos em frequência baixa — nem 'gosto' nem 'critical' são precisos. → recalibrar para gto_mixed/minor quando a mão está no mix de 3-bet."),
 dict(h=62, cards="AJs", pos="UTG", spot="Fold vs shove de 23bb",
      quote="“Normalmente aqui é fold… VPIP 15, 3-bet 4. Pode foldar tranquilo.”",
      coach="FOLD (read: nit)", system="CALL (fold = clear_mistake, EV −1.22bb)",
      ind="facing 23bb · vilão VPIP 15/3bet 4", status="diverge", fonte="coach",
      why="Caso-modelo de stats > baseline: vs população, AJs paga 23bb (+1.22bb); vs ESTE vilão (3-bet 4%), o fold do coach é claramente melhor. Nosso sistema acerta o baseline mas não usa o perfil do vilão — é exatamente o que o HUD de oponentes (fase 2+) vai cobrir."),
 dict(h=64, cards="Q8s", pos="BTN", spot="Open fold no BTN",
      quote="“Não vejo motivos para foldar… o raise para dois aqui estaria legal.”",
      coach="RAISE", system="RAISE (fold = small_mistake, EV −0.50bb)",
      ind="EV −0.50bb", status="match", fonte="ambos",
      why="Coach e sistema corrigem o hero juntos, com EV na mesa."),
 dict(h=65, cards="KK", pos="BTN", spot="Pot control com KK em board de Ás",
      quote="“Controlou o pote, não deu c-bet com par de rei no bote com Ás. Importante isso.”",
      coach="CHECK flop · CALL river", system="CHECK-ish · FOLD river (mixed)",
      ind="board Ad 9d 4s 9c 7s", status="parcial", fonte="ambos",
      why="Linha geral idêntica (pot control); no river o solver mixa fold/call e o coach pende pro call pelo range polarizado do vilão. Diferença de frequência, não de conceito."),
 dict(h=78, cards="JJ", pos="CO", spot="Shove no flop 9-T-5",
      quote="“Aqui eu vou dar o win já… o pote tá muito perto de um SPR [de 1].”",
      coach="JAM (SPR ~1)", system="CHECK (shove = clear_mistake)",
      ind="pote 13.3bb · ~19bb atrás", status="diverge", fonte="coach",
      why="Com SPR ≈ 1.4 e overpair, get-it-in é padrão de torneio; o check do nosso nó provavelmente vem de solve com stack errado (aproximação de depth). Vantagem argumentativa do coach aqui. → conferir se o nó usado respeita o stack efetivo curto."),
 dict(h=84, cards="A5o", pos="BB", spot="Shove vs limp (20bb)",
      quote="“Tá, ele limpou, a win. Justo, gosto.”",
      coach="JAM", system="CHECK (shove = small_mistake, heurística)",
      ind="20bb · pote limpado · sem GTO", status="diverge", fonte="coach",
      why="Limp-attack com Ax a 20bb é linha padrão de MTT. De novo o ponto cego de POTES LIMPADOS (mesmo do iso ATo): sem range dedicada, a heurística subestima agressão correta."),
 dict(h=85, cards="KQo", pos="CO", spot="Call no turn com overcards em board de flush",
      quote="“Você vai ter que foldar. Você deu call ainda? Não gosto.”",
      coach="FOLD", system="FOLD (call = clear_mistake, EV −2.48bb)",
      ind="EV −2.48bb", status="match", fonte="ambos",
      why="Match com EV alto: pagar sem equity em board monotone custou caro e os dois marcaram."),
 dict(h=81, cards="QQ", pos="BTN", spot="5-bet shove vs 3-bet",
      quote="“40 blinds dá para dar forbet 16, 17… quiser dar [all-in] pode também.”",
      coach="4-BET (jam aceitável)", system="JAM (gto_correct)",
      ind="41bb", status="match", fonte="ambos",
      why="Sistema valida o jam como ótimo; coach prefere 4-bet menor mas aceita — mesma região de EV."),
 dict(h=94, cards="AQo", pos="SB", spot="Bet de valor com quadra no board",
      quote="“Você deu limp e fez o nuts no river… apostou por valor e tomou call. Muito bem.”",
      coach="BET valor", system="BET (gto_correct)",
      ind="board 3h 6d 6c 6s 6h", status="match", fonte="ambos", why="Unânime."),
]

# ── Stats agregadas do torneio (direto do banco) ─────────────────────────────
conn = sqlite3.connect(DB, timeout=10); conn.row_factory = sqlite3.Row
conn.execute('PRAGMA busy_timeout=8000')
rows = [dict(r) for r in conn.execute("SELECT * FROM decisions WHERE tournament_id=? ORDER BY id", (TID,))]
conn.close()

tot = len(rows)
lblc = Counter(r['label'] for r in rows)
gtoc = Counter((r.get('gto_label') or 'sem_gto') for r in rows)
ev_total = sum(r['ev_loss_bb'] for r in rows if r.get('ev_loss_bb'))
cov = sum(1 for r in rows if r.get('gto_label'))

sc = Counter(e['status'] for e in E)
fc = Counter(e['fonte'] for e in E)

STATUS_META = {
    'match':   ('MATCH',       '#10b981', 'rgba(16,185,129,.12)'),
    'parcial': ('PARCIAL',     '#60a5fa', 'rgba(96,165,250,.12)'),
    'diverge': ('DIVERGÊNCIA', '#f59e0b', 'rgba(245,158,11,.12)'),
    'bug':     ('CALIBRAR',    '#ef4444', 'rgba(239,68,68,.12)'),
}
FONTE_LABEL = {'ambos': 'ambos defensáveis', 'sistema': 'sistema favorecido',
               'coach': 'coach favorecido', 'investigar': 'investigar'}

def card_html(e):
    s_lbl, s_col, s_bg = STATUS_META[e['status']]
    return f"""
    <div class="hand">
      <div class="hand-head">
        <span class="hand-id">MÃO #{e['h']}</span>
        <span class="hand-cards">{e['cards']} · {e['pos']}</span>
        <span class="hand-spot">{e['spot']}</span>
        <span class="badge" style="color:{s_col};background:{s_bg};border:1px solid {s_col}55">{s_lbl}</span>
      </div>
      <div class="quote">🎙 {e['quote']}</div>
      <div class="grid2">
        <div class="panel coach"><div class="panel-t">COACH</div>{e['coach']}</div>
        <div class="panel system"><div class="panel-t">GRINDLAB</div>{e['system']}<div class="ind">{e['ind']}</div></div>
      </div>
      <div class="verdict"><span class="verdict-t">Veredito ({FONTE_LABEL[e['fonte']]}):</span> {e['why']}</div>
    </div>"""

cards = '\n'.join(card_html(e) for e in E)

html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>GrindLab × Coach Review — Torneio #27 (Big $22)</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root {{ --bg:#0A0E1A; --card:#0F1526; --ring:#1E2A45; --teal:#2DD4BF; --txt:#E3E8EC; --mut:#8B96A8; }}
  * {{ box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--txt); font:14px/1.55 'Segoe UI',system-ui,sans-serif; margin:0; padding:32px 16px; }}
  .wrap {{ max-width:980px; margin:0 auto; }}
  h1 {{ font-size:22px; letter-spacing:.5px; }} h1 b {{ color:var(--teal); }}
  .sub {{ color:var(--mut); font-size:12px; margin-bottom:24px; }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:18px 0 28px; }}
  .stat {{ background:var(--card); border:1px solid var(--ring); border-radius:12px; padding:12px 14px; }}
  .stat .v {{ font-size:22px; font-weight:700; font-variant-numeric:tabular-nums; }}
  .stat .l {{ font-size:10px; text-transform:uppercase; letter-spacing:.12em; color:var(--mut); margin-top:2px; }}
  h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.15em; color:var(--teal); margin:34px 0 12px; }}
  .hand {{ background:var(--card); border:1px solid var(--ring); border-radius:14px; padding:16px 18px; margin-bottom:14px; }}
  .hand-head {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:8px; }}
  .hand-id {{ font-family:Consolas,monospace; font-size:11px; color:var(--mut); }}
  .hand-cards {{ font-family:Consolas,monospace; font-weight:700; color:var(--teal); }}
  .hand-spot {{ font-size:12px; color:var(--txt); flex:1; }}
  .badge {{ font-family:Consolas,monospace; font-size:10px; font-weight:700; letter-spacing:.08em; padding:3px 10px; border-radius:999px; }}
  .quote {{ font-style:italic; color:#b9c2d0; font-size:12.5px; border-left:3px solid var(--ring); padding-left:10px; margin:8px 0 12px; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
  @media (max-width:640px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
  .panel {{ border-radius:10px; padding:10px 12px; font-size:13px; }}
  .panel-t {{ font-family:Consolas,monospace; font-size:9px; letter-spacing:.15em; margin-bottom:4px; opacity:.8; }}
  .coach {{ background:rgba(245,158,11,.07); border:1px solid rgba(245,158,11,.25); }} .coach .panel-t {{ color:#f59e0b; }}
  .system {{ background:rgba(45,212,191,.07); border:1px solid rgba(45,212,191,.25); }} .system .panel-t {{ color:var(--teal); }}
  .ind {{ font-family:Consolas,monospace; font-size:10.5px; color:var(--mut); margin-top:5px; }}
  .verdict {{ margin-top:10px; font-size:12.5px; color:#cfd6e0; border-top:1px dashed var(--ring); padding-top:9px; }}
  .verdict-t {{ color:var(--teal); font-weight:600; }}
  .callout {{ background:rgba(239,68,68,.06); border:1px solid rgba(239,68,68,.3); border-radius:12px; padding:14px 16px; margin:10px 0; font-size:13px; }}
  .callout.ok {{ background:rgba(16,185,129,.06); border-color:rgba(16,185,129,.3); }}
  ul {{ margin:6px 0; padding-left:20px; }} li {{ margin:5px 0; }}
  .foot {{ color:var(--mut); font-size:11px; margin-top:30px; border-top:1px solid var(--ring); padding-top:12px; }}
</style></head><body><div class="wrap">

<h1><b>GrindLab</b> × Review do Coach — Torneio #27 (Big $22 · PokerStars)</h1>
<div class="sub">Validação cruzada: cada veredito do coach no vídeo foi associado ao spot correspondente e comparado com a avaliação
do engine + GTO Solver da GrindLab. Associação por ordem cronológica + âncoras de cartas/board ({len(E)} spots com comentário
substantivo associados em alta confiança).</div>

<div class="stats">
  <div class="stat"><div class="v">{tot}</div><div class="l">decisões avaliadas</div></div>
  <div class="stat"><div class="v">{cov*100//tot}%</div><div class="l">cobertura GTO</div></div>
  <div class="stat"><div class="v">−{ev_total:.0f}bb</div><div class="l">EV total deixado na mesa</div></div>
  <div class="stat"><div class="v" style="color:#10b981">{sc['match']}</div><div class="l">match com o coach</div></div>
  <div class="stat"><div class="v" style="color:#60a5fa">{sc['parcial']}</div><div class="l">parcial</div></div>
  <div class="stat"><div class="v" style="color:#f59e0b">{sc['diverge']}</div><div class="l">divergências</div></div>
  <div class="stat"><div class="v" style="color:#ef4444">{sc['bug']}</div><div class="l">itens de calibração</div></div>
</div>

<h2>Leitura executiva</h2>
<div class="callout ok"><b>Onde convergimos:</b> nos erros caros o alinhamento é alto — c-bet multiway, calls sem equity,
raises que cortam blefs, pot control com mão forte em board perigoso e os spots triviais de valor. Nos {sc['match']} matches,
{sum(1 for e in E if e['status']=='match' and 'EV' in e['ind'])} têm EV quantificado pelo solve hand-aware — o número que o coach
estima de cabeça, nós medimos.</div>
<div class="callout"><b>Onde divergimos com argumento:</b> (1) <b>GTO × exploit</b> — o coach ajusta para o field recreativo
(bluff-catch de Ás-high, fold exploitativo vs nit com VPIP 15); nosso baseline é o equilíbrio. As duas coisas são
complementares — e a leitura por stats do vilão é exatamente o roadmap do nosso HUD de oponentes. (2) <b>3-bet light de
blinds</b> — o coach adora, nós rotulamos 'critical'; o solver mixa essas mãos em frequência baixa, então a severidade certa
é 'mixed/minor'. (3) <b>Bluff-catchers com preço</b> — 88 no turn (−2.09bb) e 99 no river: o solver defende por frequência
onde o coach folda por leitura; matematicamente estamos certos no baseline.</div>
<div class="callout"><b>O que vamos calibrar (achados desta validação):</b>
<ul>
<li><b>Leitura de força de mão em 2 nós postflop</b>: wheel A-5 (mão #22) e full house (mão #37) receberam indicação de fold —
provável mismatch de nó/board no lookup. Prioridade máxima.</li>
<li><b>Labels inconsistentes</b>: ação do hero igual ao best do solver mas rotulada gto_critical (mãos #16 e #57) — o rotulador
mistura EV hand-aware com ação agregada.</li>
<li><b>Potes limpados sem range dedicada</b>: iso-raise vs limper (ATo) e limp-attack jam (A5o, 20bb) avaliados por heurística
conservadora demais.</li>
<li><b>Heurística sem cobertura GTO agressiva/medrosa</b>: ATs 'raise' vs squeeze (#15) e par de J 'fold' vs meia aposta (#35).</li>
<li><b>Severidade ∝ EV</b>: defesa de 75o no BB custou 0.04bb e levou selo 'critical' — severidade deve escalar com o EV medido.</li>
<li><b>Fronteira do RFI de BTN</b>: J8o aprovado pelo nosso preflop DB; charts padrão foldam (#51).</li>
</ul></div>

<h2>Spot a spot — coach × GrindLab</h2>
{cards}

<div class="foot">Gerado pela GrindLab a partir do hand history importado (123 mãos · {tot} decisões) e da transcrição do review.
Indicadores: EV em big blinds via solve hand-aware do GTO Solver; severidade pelo rotulador do engine v11.
Os {len(E)} spots acima são os com comentário substantivo do coach e associação de alta confiança — saudações triviais,
fold rápidos sem comentário e segmentos ambíguos da transcrição automática ficaram de fora por honestidade metodológica.</div>
</div></body></html>"""

io.open(OUT, 'w', encoding='utf-8').write(html)
print(f"OK: {OUT}")
print(f"entradas={len(E)} status={dict(sc)} fontes={dict(fc)}")
print(f"torneio: {tot} decisões, cobertura GTO {cov*100//tot}%, EV total -{ev_total:.0f}bb")
