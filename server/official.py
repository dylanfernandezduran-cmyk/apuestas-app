"""Probabilidad oficial NRNM: UNA probabilidad calibrada por mercado.

Cómo se combinan las entradas (modelo crudo, mercado sin vig, simulación):
  1. Ganador (ML/1X2) = w·modelo + (1−w)·mercado s/vig de la casa con precio (w = 50% × min(1, juegos/100); el modelo se recorta a ±20 pp del mercado).
  2. Total (línea principal) = la misma mezcla con el s/vig del total.
  3. Distribución calibrada: se mueven las medias del modelo (margen y total; en fútbol, los goles esperados λ) hasta que la distribución
     reproduce EXACTAMENTE las probabilidades oficiales de 1 y 2. De esa misma distribución salen el hándicap (NBA/NFL/NHL/MLB), totales a
     otras líneas, el marcador proyectado, el marcador exacto y la simulación Monte Carlo. Así ninguna salida contradice a otra.
Esa probabilidad oficial es la que usan EV, candados, picks, parlay y chat. El modelo crudo y el mercado s/vig se muestran sólo como entradas.
"""
from __future__ import annotations
import math
from .odds import norm_cdf
from . import model as M

def _ppf(p):
    p = min(1 - 1e-9, max(1e-9, p)); lo, hi = -9.0, 9.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if norm_cdf(mid) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def _solve(f, target, lo, hi):
    """f creciente; busca x con f(x)=target (bisección)."""
    for _ in range(80):
        mid = (lo + hi) / 2
        if f(mid) < target: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def _ml(cands):
    return {c["side"]: float(c["p_final"]) for c in cands or [] if c.get("market") == "ML" and c.get("p_final") is not None}

def _tot(cands):
    for c in cands or []:
        if c.get("market") == "Total" and c.get("side") == "over" and c.get("p_final") is not None and c.get("line") is not None:
            return float(c["line"]), float(c["p_final"])
    return None

def _soccer_mat(lh, la):
    ph, pa = M.pois_pmf(lh), M.pois_pmf(la)
    mat = [[a * b for b in pa] for a in ph]; z = sum(map(sum, mat))
    return [[x / z for x in r] for r in mat]

def _soccer_p(lh, la):
    mat = _soccer_mat(lh, la); n = len(mat)
    h = sum(mat[i][j] for i in range(n) for j in range(n) if i > j)
    a = sum(mat[i][j] for i in range(n) for j in range(n) if i < j)
    return h, a

def calibrate(mdl, cands, fam):
    """-> (mdl_cal, info) o (mdl, None). mdl_cal tiene el mismo formato que el modelo (mu, exp_total, p_home, cover, total...)."""
    if not mdl or fam == "tennis": return mdl, None
    ml = _ml(cands); tl = _tot(cands)
    if mdl.get("kind") == "margen":
        sg, ts = float(mdl["sigma"]), float(mdl["tsigma"])
        ph = ml.get("home")
        if ph is None and ml.get("away") is not None: ph = 1 - ml["away"]
        mu = sg * _ppf(ph) if ph is not None else float(mdl["mu"])
        T = float(mdl["exp_total"])
        if tl:
            L, po = tl
            T = _solve(lambda x: M.cover_normal(x, ts, L)[0], po, L - 6 * ts, L + 6 * ts)
        p_home = 1 - norm_cdf(-mu / sg)
        cal = dict(mdl, mu=mu, exp_total=T, p_home=p_home, p_away=1 - p_home,
                   cover=lambda t: M.cover_normal(mu, sg, t), total=lambda t: M.cover_normal(T, ts, t), calibrated=True)
        info = dict(kind="margen", exp_margin=mu, exp_total=T, sigma=sg, tsigma=ts, raw_margin=mdl.get("mu"), raw_total=mdl.get("exp_total"),
                    home=(T + mu) / 2, away=(T - mu) / 2)
        return cal, info
    if mdl.get("kind") == "poisson":
        th, ta = ml.get("home"), ml.get("away")
        lh, la = float(mdl["lam_home"]), float(mdl["lam_away"])
        if th is not None and ta is not None:
            s = th + ta + ml.get("draw", 1 - th - ta); th, ta = th / s, ta / s
            for _ in range(40):                       # Newton 2D con jacobiano numérico
                h, a = _soccer_p(lh, la); e1, e2 = h - th, a - ta
                if abs(e1) < 1e-6 and abs(e2) < 1e-6: break
                d = 1e-4
                h1, a1 = _soccer_p(lh + d, la); h2, a2 = _soccer_p(lh, la + d)
                J = [[(h1 - h) / d, (h2 - h) / d], [(a1 - a) / d, (a2 - a) / d]]
                det = J[0][0] * J[1][1] - J[0][1] * J[1][0]
                if abs(det) < 1e-12: break
                dl = (e1 * J[1][1] - e2 * J[0][1]) / det; da = (J[0][0] * e2 - J[1][0] * e1) / det
                lh = min(6, max(0.05, lh - dl)); la = min(6, max(0.05, la - da))
        mat = _soccer_mat(lh, la); n = len(mat)
        pw = sum(mat[i][j] for i in range(n) for j in range(n) if i > j); pd = sum(mat[i][i] for i in range(n))
        cal = dict(mdl, lam_home=lh, lam_away=la, exp_total=lh + la, mu=lh - la, p_home=pw, p_draw=pd, p_away=1 - pw - pd,
                   p_btts=sum(mat[i][j] for i in range(1, n) for j in range(1, n)),
                   cover=lambda t: M.cover_matrix(mat, lambda i, j: i - j, t), total=lambda t: M.cover_matrix(mat, lambda i, j: i + j, t), calibrated=True)
        info = dict(kind="poisson", lam_home=lh, lam_away=la, exp_margin=lh - la, exp_total=lh + la, raw_lam_home=mdl.get("lam_home"), raw_lam_away=mdl.get("lam_away"),
                    home=lh, away=la)
        return cal, info
    return mdl, None

def _recand(c, p_off):
    """Recalcula EV/edge/justa/máximo de un candidato con la probabilidad oficial (sin tocar el modelo crudo)."""
    x = M._cand(c["market"], c["side"], c["label"], c.get("price"), p_off, c.get("p_nv"), 1.0, line=c.get("line"))
    for k in ("p_final", "ev", "edge", "fair", "fair_txt", "max_price", "max_txt"): c[k] = x[k]
    c["status"] = M.status_for(c["edge"], c["ev"]); c["p_src"] = "calibrada"

def apply(cands, cal, fam):
    """Hándicap (deportes de margen) y totales fuera de la línea ancla: probabilidad de la distribución calibrada."""
    if not cal or not cal.get("calibrated") or cal.get("kind") != "margen": return
    anchor = _tot(cands)
    for c in cands or []:
        if c.get("line") is None or (c["line"] * 4) % 2 != 0: continue
        if c.get("market") == "Spread":
            L = c["line"]; p = cal["cover"](-L)[0] if c["side"] == "home" else cal["cover"](L)[1]
            _recand(c, p)
        elif c.get("market") == "Total" and anchor and c["line"] != anchor[0]:
            p = cal["total"](c["line"])[0 if c["side"] == "over" else 1]; _recand(c, p)

def summary(mdl, cal, info, cands, w):
    """Bloque `official` del análisis: probabilidades oficiales + entradas secundarias + explicación de una línea."""
    if info is None: return None
    ml = _ml(cands); mk = {}
    if ml: mk["ml"] = ml
    for c in cands or []:
        if c.get("market") == "Spread" and c.get("side") == "home": mk["spread"] = dict(line=c["line"], home=c["p_final"], away=1 - c["p_final"])
        if c.get("market") == "Total" and c.get("side") == "over": mk["total"] = dict(line=c["line"], over=c["p_final"], under=1 - c["p_final"])
    wp = round((w or 0) * 100)
    expl = (f"Probabilidad oficial NRNM = {wp}% modelo + {100 - wp}% mercado sin vig (el peso del modelo crece con los juegos jugados, máx. 50%). "
            "La distribución del marcador se recentra para reproducir esa probabilidad; de ahí salen hándicap, marcador proyectado y simulación.")
    if info.get("kind") == "poisson":
        expl = (f"Probabilidad oficial NRNM = {wp}% modelo + {100 - wp}% mercado sin vig en 1X2 (peso del modelo según juegos jugados, máx. 50%). "
                "Los goles esperados se recalibran para reproducir ese 1X2; de ahí salen marcador proyectado y simulación.")
    return dict(markets=mk, cal=info, w_model=w, explain=expl)

def lookup(cands, cal, fam):
    """f(mkt, side, line) -> probabilidad oficial (candidato a la misma línea; si no, la distribución calibrada en deportes de margen)."""
    tab = {}
    for c in cands or []:
        if c.get("p_final") is None: continue
        tab[(str(c.get("market")).lower(), c.get("side"), c.get("line"))] = float(c["p_final"])
    def f(mkt, side, line):
        k = (mkt, side, line if mkt != "ml" else None)
        if k in tab: return tab[k]
        if not cal or not cal.get("calibrated") or line is None or (line * 4) % 2 != 0: return None
        if cal.get("kind") == "margen":
            if mkt == "spread": return cal["cover"](-line)[0] if side == "home" else cal["cover"](line)[1]
            if mkt == "total": return cal["total"](line)[0 if side == "over" else 1]
        return None
    return f
