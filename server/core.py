"""Equivalentes Python del núcleo JS (static/nrnm-core.js). Misma semántica."""
import math

DIVERGENCE_MAX_PP = 10
MAX_W = 0.5
N0 = 100
MAX_GAP = 0.20

def implied(o):
    o = float(o)
    return -o / (-o + 100) if o < 0 else 100 / (o + 100)

def decimal(o):
    o = float(o)
    return 1 + 100 / -o if o < 0 else 1 + o / 100

def fair_odds(p):
    p = float(p)
    return int(round(-100 * p / (1 - p))) if p >= 0.5 else int(round(100 * (1 - p) / p))

def no_vig(o_a, o_b):
    a, b = implied(o_a), implied(o_b)
    s = a + b
    return [a / s, b / s]

def ev(p, o):
    return float(p) * decimal(o) - 1

def edge_pp(p_final, p_no_vig):
    return (float(p_final) - float(p_no_vig)) * 100

def kelly(p, o):
    d = decimal(o)
    return max(0.0, (float(p) * d - 1) / (d - 1))

def stake_pct(p, o, frac=0.25, cap=0.02):
    return min(cap, kelly(p, o) * frac)

def clamp(x, lo, hi):
    return min(hi, max(lo, x))

def p_final(p_model, p_market, n_games, max_w=MAX_W, n0=N0, max_gap=MAX_GAP):
    w = max_w * min(1.0, float(n_games) / n0)
    pm = clamp(float(p_model), float(p_market) - max_gap, float(p_market) + max_gap)
    return w * pm + (1 - w) * float(p_market)

def pick_state(edge, ev_val, conf, gap_pp):
    conf_l = (conf or "").lower()
    if gap_pp is not None and gap_pp > DIVERGENCE_MAX_PP:
        return "REVISAR"
    if edge is not None and edge >= 3 and (ev_val or 0) >= 0 and conf_l != "baja":
        return "PICK"
    if edge is not None and edge >= 1:
        return "LEAN"
    return "PASS"

def parlay(legs):
    dec = 1.0
    p_model = 1.0
    p_imp = 1.0
    for l in legs:
        dec *= decimal(l["odds"])
        p_model *= float(l["pModel"] if "pModel" in l else l.get("p_model"))
        p_imp *= implied(l["odds"])
    american = int(round((dec - 1) * 100)) if dec >= 2 else int(round(-100 / (dec - 1)))
    return dict(american=american, pModel=p_model, pImp=p_imp, evCap=p_model * dec - 1)

def move_pp(o_open, o_now):
    return (implied(o_now) - implied(o_open)) * 100

def median(a):
    if not a:
        return None
    s = sorted(a)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2

def _sign(x):
    if x > 0: return 1
    if x < 0: return -1
    return 0

def detect_moves(snaps, pct_tickets=None, sharp="Pinnacle", window_min=180):
    """snaps: [{book, t (ms), odds, line?}] de UN lado de UN mercado."""
    if not snaps:
        return dict(ppConsensus=None, tags=[], laggards=[], books=0)
    t_now = max(s["t"] for s in snaps)
    win = [s for s in snaps if t_now - s["t"] <= window_min * 60000]
    by_book = {}
    for s in win:
        by_book.setdefault(s["book"], []).append(s)
    moves = []
    for book, a in by_book.items():
        a = sorted(a, key=lambda x: x["t"])
        moves.append(dict(book=book, now=a[-1], open=a[0],
                          pp=move_pp(a[0]["odds"], a[-1]["odds"]),
                          line0=a[0].get("line"), line1=a[-1].get("line")))
    if not moves:
        return dict(ppConsensus=None, tags=[], laggards=[], books=0)
    cons = median([m["pp"] for m in moves])
    same = [m for m in moves if _sign(m["pp"]) == _sign(cons) and abs(m["pp"]) >= 2]
    sharp_move = next((m for m in moves if m["book"] == sharp or str(m["book"]).lower() == str(sharp).lower()), None)
    tags = []
    if abs(cons) >= 3 and len(same) >= 3 and (sharp_move is None or abs(sharp_move["pp"]) >= 2):
        tags.append("STEAM")
    if cons >= 3 and pct_tickets is not None and pct_tickets <= 0.45:
        tags.append("RLM")
    med_now = median([implied(m["now"]["odds"]) for m in moves])
    laggards = [dict(book=m["book"], odds=m["now"]["odds"])
                for m in moves if med_now - implied(m["now"]["odds"]) >= 0.02]
    if laggards:
        tags.append("REZAGADA")
    return dict(ppConsensus=cons, tags=tags, laggards=laggards, books=len(moves),
                moves=moves, open=moves[0]["open"] if moves else None)
