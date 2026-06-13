"""
Aderência coach × sistema: dado o veredito do sistema (decision) e a anotação do coach,
classifica em match / divergência. Fonte ÚNICA — usada tanto pelo relatório offline
(scripts/build_coach_report_t27.py) quanto pelo endpoint /coach/student/<id>/tournament
(marcação ao vivo das mãos não-aderentes na tela do coach).

Aceita dict ou sqlite3.Row (acesso por chave). Campos esperados:
  decision: action_taken, label, gto_label
  annotation: coach_action, coach_override_label, comment
"""
import re

SYS_MISTAKE_LABELS = {'small_mistake', 'clear_mistake'}

_APPROVE = re.compile(r'perfeit|jogou (muito )?bem|muito bem|bem jogad|aprov|(?<!n[ãa]o )gost(o|ei|a )|'
                      r'\bcerto\b|correto|\blegal\b|[óo]tim|justo|excelente|t[áa] bom|t[áa] correto|'
                      r'tranquil|sem erro|trivial|un[âa]nime|\bboa\b|\bbom\b|sem cr[íi]tica|'
                      r'beleza|passou|\bok\b|importante isso|paci[êe]ncia', re.I)
_CRIT = re.compile(r'deveria|recomendo|n[ãa]o gosto|larga(r|ria)?|pode largar|errad|for[çc]ad|desnecess|'
                   r'estranh|confus|sem sentido|pecou|abusiv|demais|problema|n[ãa]o aconselho|'
                   r'n[ãa]o recomend|cortou|caro\b|evita|\bruim|prefiro|preferia|tomaria|tem que|'
                   r'alto demais|baixo demais|n[ãa]o (faz sentido|me parece)|spew|vil[ãa]o|perde', re.I)
_STRONG_CRIT = re.compile(r'demais|n[ãa]o gosto|deveria|errad|desnecess|estranh|confus|sem sentido|'
                          r'pecou|caro\b|problema|n[ãa]o aconselho|n[ãa]o recomend|spew|cortou|abusiv|'
                          r'alto demais|baixo demais|prefiro|preferia|tomaria|n[ãa]o (faz sentido|me parece)', re.I)


def norm(a):
    a = (a or '').lower().rstrip('s')
    return {'allin': 'allin', 'all-in': 'allin', 'jam': 'allin', 'shove': 'allin',
            'bet': 'bet', 'raise': 'raise', 'call': 'call', 'fold': 'fold', 'check': 'check'}.get(a, a)


def _parse_rec(t):
    t = (t or '').lower()
    if re.search(r'\b(jam|shove|all-?in|dar(ia)? (o |a )?win|manda(r)? win|all in)\b', t): return 'allin'
    if re.search(r'\b(3-?bet|tribet|re-?raise|reraise|iso-?raise|4-?bet|forbet|5-?bet)\b', t): return 'raise'
    if re.search(r'\b(fold|larga(r|ria)?|largo|foldar(ia|am|ado)?|joga(r)? fora)\b', t): return 'fold'
    if re.search(r'\b(aposta(r|ndo)?|c-?bet|barrel|lead|donk|value|\bbet\b|blocking bet|apostei)\b', t): return 'bet'
    if re.search(r'\b(check-?call|check-?fold|dar mesa|da mesa|pot control|\bcheck\b|controlou)\b', t): return 'check'
    if re.search(r'\b(call|pagar|paga|pago|acompanha)\b', t): return 'call'
    return None


def coach_says_mistake(dec, ann):
    """True/False/None — o coach considera a jogada do hero um erro? None = comentário neutro."""
    if ann['coach_override_label']:
        return ann['coach_override_label'] in SYS_MISTAKE_LABELS
    hero = norm(dec['action_taken'])
    t = ann['comment'] or ''
    rec = norm(ann['coach_action']) if ann['coach_action'] else _parse_rec(t)
    strong = bool(_STRONG_CRIT.search(t))
    _neg_kw = {'fold': r'fold|larga', 'call': r'call|pag', 'bet': r'aposta|bet|c-?bet',
               'check': r'check|mesa', 'raise': r'3-?bet|raise|tribet', 'allin': r'all|jam|shove|win'}
    _negated = rec and re.search(r'n[ãa]o\b[^.]{0,30}(' + _neg_kw.get(rec, rec) + ')', t, re.I)
    if rec and rec == hero and not strong and not _negated:
        return False
    ap, cr = len(_APPROVE.findall(t)), len(_CRIT.findall(t))
    if ap == 0 and cr == 0:
        return None
    return cr > ap


def classify(dec, ann):
    """Categoria de aderência. 'erro do sistema' = label (severidade), não gto_label.
    Retorna (kind, coach_rec) — kind em: match_ok | match_erro | diverge_rigido |
    diverge_perdido | comentario."""
    sys_mistake = dec['label'] in SYS_MISTAKE_LABELS
    cm = coach_says_mistake(dec, ann)
    rec = norm(ann['coach_action']) if ann['coach_action'] else None
    if cm is None:
        return 'comentario', rec
    if sys_mistake and cm:        return 'match_erro', rec
    if not sys_mistake and not cm: return 'match_ok', rec
    if sys_mistake and not cm:    return 'diverge_rigido', rec
    return 'diverge_perdido', rec


def is_divergent(kind):
    return kind in ('diverge_rigido', 'diverge_perdido')
