"""Política de publicación NRNM: niveles de probabilidad y candados.
Un pick sólo se RECOMIENDA si pasa todos los candados. Los bloqueados siguen en la base de datos,
se registran y se califican igual (auditoría); sólo no se muestran como recomendación.
Días con cero picks son válidos: nunca se fuerza un pick."""
import time
from .config import MIN_PROB, AUDIT_PROB, MIN_HIST, CAL_OVER_PP, STALE_H, MIN_DQ

TIERS = [(0.0, MIN_PROB, "bloqueado", "Bloqueado"), (MIN_PROB, 0.60, "moderada", "Moderada"), (0.60, 0.70, "favorable", "Favorable"),
         (0.70, 0.80, "elevada", "Elevada"), (0.80, AUDIT_PROB, "muy_elevada", "Muy elevada"), (AUDIT_PROB, 1.01, "auditoria", "Auditoría especial")]
LOCKS = [("prob", "Probabilidad"), ("value", "Valor"), ("data", "Datos"), ("model", "Modelo"), ("consistency", "Consistencia"),
         ("calibration", "Calibración"), ("correlation", "Correlación"), ("live", "En vivo"), ("audit", "Auditoría")]
BUCKETS = [(0.0, 0.5, "<50%"), (0.5, 0.6, "50–60%"), (0.6, 0.7, "60–70%"), (0.7, 0.8, "70–80%"), (0.8, 0.9, "80–90%"), (0.9, 1.01, "≥90%")]

def tier(p):
    if p is None: return dict(key="sin_dato", label="Sin dato")
    for a, b, k, l in TIERS:
        if a <= p < b: return dict(key=k, label=l)
    return dict(key="auditoria", label="Auditoría especial")

_H = {"t": 0, "n": {}, "cal": {}}

def history(rows_fn, ttl=600):
    """Muestra calificada por deporte+mercado y calibración por cubeta (sólo picks con cuota, G/P)."""
    if time.time() - _H["t"] < ttl: return _H
    rows = rows_fn("SELECT sport, market, status, odds, p_final FROM picks WHERE status IN ('GANADO','PERDIDO') AND odds IS NOT NULL")
    n, cal = {}, {}
    for r in rows:
        k = (r.get("sport"), r.get("market")); n[k] = n.get(k, 0) + 1
        p = r.get("p_final")
        if p is None: continue
        lab = next(l for a, b, l in BUCKETS if a <= float(p) < b)
        c = cal.setdefault(lab, [0, 0, 0.0]); c[0] += 1; c[1] += r["status"] == "GANADO"; c[2] += float(p)
    _H.update(t=time.time(), n=n, cal={k: dict(n=v[0], real=100 * v[1] / v[0], pred=100 * v[2] / v[0]) for k, v in cal.items() if v[0]})
    return _H

def bucket_of(p):
    return next((l for a, b, l in BUCKETS if a <= p < b), None) if p is not None else None

def check(it, H, now=None, consistent=True, dq=None, updated_at=None, parlay=False):
    """Devuelve dict(approved, tier, locks=[{key,label,reason}]) para un pick ya con métricas (p_final, ev_pct)."""
    now = now or time.time()
    p = it.get("p_final"); ev = it.get("ev_pct"); out = []
    if p is not None and p > 1: p = p / 100.0   # las tarjetas traen p en %
    def lock(k, why): out.append(dict(key=k, label=dict(LOCKS)[k], reason=why))
    if p is None: lock("prob", "Sin probabilidad del modelo")
    elif p < MIN_PROB: lock("prob", f"Prob. NRNM {p*100:.1f}% < {MIN_PROB*100:.0f}% (mínimo configurado)")
    if ev is None or ev <= 0: lock("value", "EV ≤ 0: el precio no paga el riesgo" if ev is not None else "Sin cuota: no es pick")
    if dq is not None and dq < MIN_DQ: lock("data", f"Calidad de datos {dq}/100 < {MIN_DQ}")
    if updated_at and not it.get("live") and now - updated_at > STALE_H * 3600:
        lock("data", f"Cuota sin refrescar hace {int((now - updated_at) / 3600)} h")
    nh = H["n"].get((it.get("sport"), it.get("market")), 0)
    if nh < MIN_HIST: lock("model", f"Sólo {nh} picks calificados de {it.get('sport_name') or it.get('sport')} · {it.get('market_name') or it.get('market')} (mínimo {MIN_HIST})")
    if not consistent: lock("consistency", "El pick registrado contradice la predicción vigente")
    b = bucket_of(p); c = H["cal"].get(b) if b else None
    if c and c["n"] >= MIN_HIST and c["real"] - c["pred"] < -CAL_OVER_PP:
        lock("calibration", f"Cubeta {b}: predijo {c['pred']:.1f}% y acertó {c['real']:.1f}% (n={c['n']})")
    if parlay: lock("correlation", "Parlay: se evalúa con la probabilidad conjunta (producto de piernas)")
    if it.get("live"): lock("live", "El juego ya empezó: datos en vivo con retraso, no se recomienda")
    if p is not None and p >= AUDIT_PROB: lock("audit", f"Prob. ≥ {AUDIT_PROB*100:.0f}%: requiere revisión manual, no se aprueba solo")
    return dict(approved=not out, tier=tier(p), locks=out)

def config():
    return dict(min_prob=MIN_PROB, audit_prob=AUDIT_PROB, min_hist=MIN_HIST, cal_over_pp=CAL_OVER_PP, stale_h=STALE_H, min_dq=MIN_DQ,
                tiers=[dict(key=k, label=l, lo=a, hi=min(b, 1.0)) for a, b, k, l in TIERS])
