"""Detector STEAM / RLM / REZAGADA sobre el historial real (núcleo section 6).
Sólo se listan movimientos de consenso de al menos MIN_MOVE_PP puntos porcentuales.
Sin inventar datos: si falta historial o % tickets, no se fabrica la etiqueta."""
from . import history
from . import core as CORE

MIN_MOVE_PP = 3.0
WINDOW_MIN = 180
SHARP = "Pinnacle"

def _snaps(pts):
    """pts: [[ts_s, line, price], ...] → [{book set later, t_ms, odds, line}]"""
    out = []
    for p in pts or []:
        if not p or p[2] is None:
            continue
        try:
            odds = int(p[2])
        except (TypeError, ValueError):
            continue
        out.append(dict(t=int(p[0] * 1000), odds=odds, line=p[1]))
    return out

def _pct_tickets(splits_side):
    ticks = [s[1] for s in (splits_side or []) if s and s[1] is not None]
    if not ticks:
        return None
    # historial guarda % 0-100
    v = ticks[-1]
    return v / 100.0 if v > 1 else v

def detect(series, min_pp=MIN_MOVE_PP):
    """series: history.series(league, eid). Lista de alertas/movimientos por mercado+lado."""
    alerts = []
    lines = (series or {}).get("lines") or {}
    splits = (series or {}).get("splits") or {}
    for mk, books in lines.items():
        sides = set()
        for sd in books.values():
            sides.update(sd.keys())
        for side in sides:
            snaps = []
            open_line = now_line = None
            open_odds = now_odds = None
            last_t = 0
            for book, sd in books.items():
                pts = sd.get(side) or []
                ss = _snaps(pts)
                if not ss:
                    continue
                for s in ss:
                    s["book"] = book
                    snaps.append(s)
                if open_odds is None:
                    open_odds, open_line = ss[0]["odds"], ss[0].get("line")
                now_odds, now_line = ss[-1]["odds"], ss[-1].get("line")
                last_t = max(last_t, ss[-1]["t"])
            if len(snaps) < 2:
                continue
            pct = _pct_tickets((splits.get(mk) or {}).get(side) or [])
            det = CORE.detect_moves(snaps, pct_tickets=pct, sharp=SHARP, window_min=WINDOW_MIN)
            cons = det.get("ppConsensus")
            if cons is None or abs(cons) < min_pp:
                continue
            # apertura / actual de consenso: primer y último snap global
            snaps_sorted = sorted(snaps, key=lambda s: s["t"])
            open_odds, open_line = snaps_sorted[0]["odds"], snaps_sorted[0].get("line")
            now_odds, now_line = snaps_sorted[-1]["odds"], snaps_sorted[-1].get("line")
            last_t = snaps_sorted[-1]["t"]
            line_delta = None
            if open_line is not None and now_line is not None:
                try:
                    line_delta = float(now_line) - float(open_line)
                except (TypeError, ValueError):
                    line_delta = None
            tags = list(det.get("tags") or [])
            # etiqueta visible
            if "REZAGADA" in tags:
                tags = [("CASA REZAGADA" if t == "REZAGADA" else t) for t in tags]
            alerts.append(dict(
                kind="MOVE", market=mk, side=side,
                pp=round(cons, 2),
                open_odds=open_odds, now_odds=now_odds,
                open_line=open_line, now_line=now_line, line_delta=line_delta,
                tags=tags, books=det.get("books") or 0,
                laggards=det.get("laggards") or [],
                ts=last_t / 1000.0,
                pct_tickets=None if pct is None else round(pct * 100, 1),
            ))
    return alerts

def scan_since(since_ts, min_pp=MIN_MOVE_PP):
    keys = history.changed_since(since_ts)
    out = []
    for league, eid in keys:
        ser = history.series(league, eid)
        alerts = detect(ser, min_pp=min_pp)
        if alerts:
            out.append(dict(league=league, eid=str(eid), alerts=alerts, n_points=ser.get("n_points") or 0))
    return out
