"""Detector STEAM / RLM / REZAGADA sobre el historial real de líneas (tabla `lines` / `splits`).
Sólo se reportan movimientos de al menos MIN_MOVE_PP puntos porcentuales de prob. implícita.
Sin inventar datos: si no hay historial suficiente, no hay alerta."""
from .odds import am_to_prob
from . import history

MIN_MOVE_PP = 3.0
STEAM_WINDOW_S = 60 * 60  # movimiento brusco en <= 60 min
PUBLIC_TICKETS = 55        # umbral de lado público para RLM

def _p(price):
    if price is None: return None
    try:
        return am_to_prob(int(price))
    except (TypeError, ValueError):
        return None

def _pp(a, b):
    if a is None or b is None: return None
    return (b - a) * 100.0

def _first_last(pts):
    """pts: [[ts, line, price], ...] ordenados."""
    if not pts or len(pts) < 2:
        return None
    return pts[0], pts[-1]

def steam_in_series(pts, min_pp=MIN_MOVE_PP, window=STEAM_WINDOW_S):
    """True si en alguna ventana de `window` segundos la prob. implícita se mueve >= min_pp (abs)."""
    clean = [p for p in (pts or []) if p and p[2] is not None and _p(p[2]) is not None]
    if len(clean) < 2:
        return None
    best = None
    for i, a in enumerate(clean):
        pa = _p(a[2])
        for b in clean[i + 1:]:
            if b[0] - a[0] > window:
                break
            pp = _pp(pa, _p(b[2]))
            if pp is None:
                continue
            if abs(pp) >= min_pp and (best is None or abs(pp) > abs(best["pp"])):
                best = dict(kind="STEAM", pp=round(pp, 2), ts0=a[0], ts1=b[0],
                            price0=a[2], price1=b[2], line0=a[1], line1=b[1])
    return best

def rlm_in_market(book_pts, splits_side, min_pp=MIN_MOVE_PP, public=PUBLIC_TICKETS):
    """RLM: el público (>=public % tickets) carga un lado y la cuota/prob se mueve en su contra >= min_pp.
    book_pts: lista de series (una por casa) para ESE lado; splits_side: [[ts, tickets, money], ...]."""
    if not splits_side:
        return None
    # último % tickets conocido
    ticks = [s[1] for s in splits_side if s and s[1] is not None]
    if not ticks:
        return None
    t_last = ticks[-1]
    if t_last < public:
        return None
    # movimiento de prob. (promedio de casas, o la de más puntos)
    moves = []
    for pts in book_pts or []:
        fl = _first_last(pts)
        if not fl:
            continue
        pp = _pp(_p(fl[0][2]), _p(fl[1][2]))
        if pp is not None:
            moves.append((pp, fl[0], fl[1], pts))
    if not moves:
        return None
    # en contra del público: la prob. implícita del lado público BAJA (pp < 0)
    against = [m for m in moves if m[0] <= -min_pp]
    if not against:
        return None
    pp, a, b, _ = min(against, key=lambda x: x[0])  # la más en contra
    return dict(kind="RLM", pp=round(pp, 2), tickets=t_last, ts0=a[0], ts1=b[0],
                price0=a[2], price1=b[2], line0=a[1], line1=b[1])

def rezagada_in_market(by_book, min_pp=MIN_MOVE_PP):
    """REZAGADA: el consenso de casas se movió >= min_pp y al menos una casa no (rezago vs mediana >= min_pp).
    by_book: {book: [[ts,line,price], ...]} para el mismo mercado+lado."""
    last_p, open_p, books = {}, {}, []
    for book, pts in (by_book or {}).items():
        fl = _first_last(pts)
        if not fl:
            continue
        p0, p1 = _p(fl[0][2]), _p(fl[1][2])
        if p0 is None or p1 is None:
            continue
        open_p[book] = p0
        last_p[book] = p1
        books.append(book)
    if len(books) < 2:
        return None
    pps = [(book, (last_p[book] - open_p[book]) * 100) for book in books]
    cons = sorted(x[1] for x in pps)
    mid = cons[len(cons) // 2]
    if abs(mid) < min_pp:
        return None
    laggards = []
    for book, pp in pps:
        lag = mid - pp
        # no se movió con el consenso: rezago absoluto >= min_pp
        if abs(lag) >= min_pp and abs(pp) < min_pp:
            laggards.append(dict(book=book, pp=round(pp, 2), lag_pp=round(lag, 2)))
    if not laggards:
        return None
    return dict(kind="REZAGADA", consensus_pp=round(mid, 2), laggards=laggards)

def detect(series, min_pp=MIN_MOVE_PP):
    """series: salida de history.series(league, eid). Devuelve lista de alertas (sólo >= min_pp)."""
    alerts = []
    lines = (series or {}).get("lines") or {}
    splits = (series or {}).get("splits") or {}
    for mk, books in lines.items():
        # books: {book: {side: [pts]}}
        sides = set()
        for b, sd in books.items():
            sides.update(sd.keys())
        for side in sides:
            by_book = {book: (sd.get(side) or []) for book, sd in books.items()}
            # STEAM: cualquier casa
            for book, pts in by_book.items():
                st = steam_in_series(pts, min_pp=min_pp)
                if st:
                    st.update(market=mk, side=side, book=book)
                    alerts.append(st)
            # REZAGADA
            rz = rezagada_in_market(by_book, min_pp=min_pp)
            if rz:
                rz.update(market=mk, side=side)
                alerts.append(rz)
            # RLM
            spl = ((splits.get(mk) or {}).get(side) or [])
            r = rlm_in_market(list(by_book.values()), spl, min_pp=min_pp)
            if r:
                r.update(market=mk, side=side)
                alerts.append(r)
    # no reportar movimientos < min_pp (defensivo)
    out = []
    for a in alerts:
        pp = a.get("pp")
        if pp is None and a.get("kind") == "REZAGADA":
            if abs(a.get("consensus_pp") or 0) >= min_pp:
                out.append(a)
            continue
        if pp is not None and abs(pp) >= min_pp:
            out.append(a)
    return out

def scan_since(since_ts, min_pp=MIN_MOVE_PP):
    """Alertas de todos los juegos con cambios desde since_ts. Sin nombres de equipos (se anexan en el API)."""
    keys = history.changed_since(since_ts)
    out = []
    for league, eid in keys:
        ser = history.series(league, eid)
        alerts = detect(ser, min_pp=min_pp)
        if alerts:
            out.append(dict(league=league, eid=str(eid), alerts=alerts, n_points=ser.get("n_points") or 0))
    return out
