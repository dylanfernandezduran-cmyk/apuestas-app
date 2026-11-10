"""Modelo transparente (estimación, no certeza). Ver README para la metodología."""
import math
from .config import FAMILY, SOCCER, EDGE_PICK, EDGE_LEAN, MIN_EV_MARGIN
from .odds import am_to_dec, am_to_prob, prob_to_am, fmt_am, norm_cdf

# ---------- helpers de probabilidad ----------
def pois_pmf(l, kmax=12):
    p = [math.exp(-l)]
    for k in range(1, kmax + 1): p.append(p[-1] * l / k)
    return p

def cover_normal(mu, sigma, t):
    """P(X > t) para X entero ~ N(mu, sigma) (con corrección de continuidad). Excluye push. Devuelve (win, loss, push_aprox)."""
    if float(t).is_integer():
        win = 1 - norm_cdf((t + 0.5 - mu) / sigma)
        loss = norm_cdf((t - 0.5 - mu) / sigma)
        push = max(0.0, 1 - win - loss)
        z = win + loss
        return win / z, loss / z, push
    win = 1 - norm_cdf((t - mu) / sigma)
    return win, 1 - win, 0.0

def cover_matrix(mat, f, t):
    """mat[i][j] prob (i goles local, j visita). f(i,j)-> valor entero; P(f > t) excluyendo push."""
    win = loss = push = 0.0
    for i, row in enumerate(mat):
        for j, p in enumerate(row):
            v = f(i, j)
            if v > t: win += p
            elif v < t: loss += p
            else: push += p
    z = win + loss
    return (win / z, loss / z, push) if z > 0 else (0.5, 0.5, push)

# ---------- modelos ----------
# NFL: starting QB out is a large, documented rating hit. Public models often use ~3–6 pts of spread;
# we use a conservative mid-range (4.5 pts of margin against the team, ~2 pts off the total).
NFL_QB_OUT_MARGIN = 4.5
NFL_QB_OUT_TOTAL = 2.0
DIVERGENCE_HIGH = 0.10          # |p_model_raw − p_nv| > 10 pp → bandera, no PICK/estrella
CONF_RANK = {"Alta": 2, "Media": 1, "Baja": 0}

def margin_model(R, hid, aid, neutral=False, extra_margin=0.0, extra_total=0.0):
    fam = FAMILY[R["family"]]
    rh, ra = R["rating"].get(hid), R["rating"].get(aid)
    if rh is None or ra is None: return None
    hfa = 0.0 if neutral else R["hfa"]
    mu = rh - ra + hfa + extra_margin
    sigma = fam["sigma"]
    l = R["lg_pts"]
    exp_total = ((R["off"][hid] + R["def"][aid]) / 2) + ((R["off"][aid] + R["def"][hid]) / 2) + extra_total
    p_home = cover_normal(mu, sigma, 0)[0] if not float(0).is_integer() else None
    # P(gana local): margen > 0 (sin empates en estos deportes; en NFL los empates son raros)
    p_home = 1 - norm_cdf((0 - mu) / sigma)
    n_h, n_a = R["n"].get(hid, 0), R["n"].get(aid, 0)
    sample = min(1.0, min(n_h, n_a) / fam["n_full"])
    return dict(kind="margen", mu=mu, sigma=sigma, tsigma=fam["tsigma"], exp_total=exp_total, p_home=p_home, p_away=1 - p_home,
                p_draw=None, hfa=hfa, rating_home=rh, rating_away=ra, n_home=n_h, n_away=n_a, sample=sample,
                cover=lambda t: cover_normal(mu, sigma, t),
                total=lambda t: cover_normal(exp_total, fam["tsigma"], t))

def soccer_model(R, hid, aid, neutral=False):
    if hid not in R["att"] or aid not in R["att"]: return None
    lh_base, la_base = R["lg_home"], R["lg_away"]
    if neutral: lh_base = la_base = (lh_base + la_base) / 2
    lh = lh_base * R["att"][hid] * R["def"][aid]
    la = la_base * R["att"][aid] * R["def"][hid]
    ph, pa = pois_pmf(lh), pois_pmf(la)
    mat = [[a * b for b in pa] for a in ph]
    tot = sum(sum(r) for r in mat)
    mat = [[x / tot for x in r] for r in mat]
    pw = sum(mat[i][j] for i in range(len(mat)) for j in range(len(mat)) if i > j)
    pd = sum(mat[i][i] for i in range(len(mat)))
    pl = 1 - pw - pd
    n_h, n_a = R["n"].get(hid, 0), R["n"].get(aid, 0)
    sample = min(1.0, min(n_h, n_a) / SOCCER["n_full"])
    pb = sum(mat[i][j] for i in range(1, len(mat)) for j in range(1, len(mat)))      # ambos anotan
    return dict(kind="poisson", lam_home=lh, lam_away=la, exp_total=lh + la, mu=lh - la, p_home=pw, p_draw=pd, p_away=pl, p_btts=pb,
                n_home=n_h, n_away=n_a, sample=sample, hfa=None,
                cover=lambda t: cover_matrix(mat, lambda i, j: i - j, t),
                total=lambda t: cover_matrix(mat, lambda i, j: i + j, t),
                mat_top=sorted(((i, j, mat[i][j]) for i in range(7) for j in range(7)), key=lambda x: -x[2])[:5])

def tennis_model(pa, pb, p_mkt_home=None):
    """pa/pb: puntos ranking ATP/WTA. Logística sobre ln(puntos). Heurística simple.
    Si falta el ranking de uno (lucky loser / wild card / junior), no se apaga el modelo:
    se imputan puntos bajos o se calibran con el ML de mercado cuando existe."""
    UNRANKED = 20.0   # ~fuera del top 500; se marca sample bajo
    imputed = False
    if not pa and not pb: return None
    if not pa or not pb:
        imputed = True
        known = pa or pb
        if p_mkt_home is not None and 0.02 < p_mkt_home < 0.98 and known:
            # invierte la logística para que p_home ≈ mercado
            logit = math.log(p_mkt_home / (1 - p_mkt_home))
            # p = 1/(1+e^{-0.8 ln(pa/pb)}) => ln(pa/pb)=logit/0.8
            ratio = math.exp(logit / 0.8)
            if not pa: pa = max(5.0, known * ratio)
            else: pb = max(5.0, known / ratio)
        else:
            if not pa: pa = UNRANKED
            if not pb: pb = UNRANKED
    d = math.log(pa / pb)
    p = 1 / (1 + math.exp(-0.8 * d))
    return dict(kind="ranking", p_home=p, p_away=1 - p, p_draw=None, mu=None, exp_total=None,
                sample=0.25 if imputed else 0.5, hfa=None, n_home=None, n_away=None, imputed=imputed)

# ---------- candidatos ----------
def blend_weight(model):
    """Peso del modelo en la mezcla final (resto = mercado sin vig). Máx 0.5; menor con muestra chica."""
    return 0.5 * model["sample"]

MAX_GAP = 0.20   # el modelo no puede alejarse más de 20 pp del mercado (recorte de seguridad)

def _cand(market, side, label, price, p_model, p_nv, w, line=None):
    p_raw = p_model
    if p_nv is not None: p_model = max(p_nv - MAX_GAP, min(p_nv + MAX_GAP, p_model))
    p_final = w * p_model + (1 - w) * p_nv if p_nv is not None else p_model
    dec = am_to_dec(price) if price is not None else None
    ev = (p_final * dec - 1) if dec else None
    edge = (p_final - p_nv) * 100 if p_nv is not None else None
    fair = prob_to_am(p_final)
    maxp = prob_to_am(min(0.999, p_final - MIN_EV_MARGIN * p_final)) if False else None
    # precio máximo: momio donde EV = +2% => dec_min = 1.02 / p_final
    dec_min = (1 + MIN_EV_MARGIN) / p_final if p_final > 0 else None
    max_am = None
    if dec_min and dec_min > 1:
        pp = 1 / dec_min
        max_am = prob_to_am(pp)
    div = abs(p_raw - p_nv) * 100 if p_nv is not None and p_raw is not None else None
    return dict(market=market, side=side, label=label, line=line, price=price, price_txt=fmt_am(price),
                p_model=p_model, p_model_raw=p_raw, clipped=(abs(p_raw - p_model) > 1e-9), p_nv=p_nv, p_final=p_final, edge=edge, ev=(ev * 100 if ev is not None else None),
                fair=fair, fair_txt=fmt_am(fair), max_price=max_am, max_txt=fmt_am(max_am),
                implied_raw=(am_to_prob(price) if price is not None else None),
                divergence=div, divergence_high=(div is not None and div > DIVERGENCE_HIGH * 100))

def status_for(edge, ev):
    if edge is None: return "SIN_LINEA"
    if edge >= EDGE_PICK and (ev or 0) >= 0: return "PICK"
    if edge >= EDGE_LEAN: return "LEAN"
    return "PASS"

def build_candidates(model, odds, home_name, away_name):
    """Devuelve lista de candidatos (todos los mercados con precio)."""
    c = []
    w = blend_weight(model)
    nv = (odds or {}).get("nv", {})
    if odds:
        ml = odds["ml"]; nvm = nv.get("ml", {})
        for side, nm, key in (("home", home_name, "p_home"), ("away", away_name, "p_away"), ("draw", "Empate", "p_draw")):
            if side in ml and model.get(key) is not None:
                c.append(_cand("ML", side, f"{nm} ML" if side != "draw" else "Empate (1X2)", ml[side], model[key], nvm.get(side), w))
        sp = odds["spread"]; nvs = nv.get("spread", {})
        if "cover" in model:
            for side, nm in (("home", home_name), ("away", away_name)):
                if side in sp:
                    L = sp[side]["line"]
                    if (L * 4) % 2 != 0: continue   # líneas de cuarto: sin modelar
                    if side == "home": win = model["cover"](-L)[0]
                    else:
                        # visitante cubre si (j - i) > -L  <=> (i - j) < L
                        win = model["cover"](L)[1]
                    ln = f"{L:+g}"
                    c.append(_cand("Spread", side, f"{nm} {ln}", sp[side]["price"], win, nvs.get(side), w, line=L))
            tt = odds["total"]; nvt = nv.get("total", {})
            for side, nm in (("over", "Over"), ("under", "Under")):
                if side in tt:
                    T = tt[side]["line"]
                    if (T * 4) % 2 != 0: continue
                    win = model["total"](T)[0] if side == "over" else model["total"](T)[1]
                    c.append(_cand("Total", side, f"{nm} {T:g}", tt[side]["price"], win, nvt.get(side), w, line=T))
    bt = (odds or {}).get("btts") or {}
    if bt and model.get("p_btts") is not None:                     # ambos anotan (fútbol): cuota real de DraftKings vía ESPN
        nvb = nv.get("btts", {})
        for side, nm in (("yes", "Ambos anotan: Sí"), ("no", "Ambos anotan: No")):
            if bt.get(side) is not None:
                c.append(_cand("BTTS", side, nm, bt[side], model["p_btts"] if side == "yes" else 1 - model["p_btts"], nvb.get(side), w))
    for x in c: x["status"] = status_for(x["edge"], x["ev"])
    return c

def confidence(model, odds, flags, family):
    """Nivel de confianza 🟢/🟡/🔴 según muestra, divergencia vs mercado, lesiones clave y datos."""
    score = 0
    s = model["sample"]
    score += 2 if s >= 0.85 else (1 if s >= 0.45 else 0)
    reasons = []
    if s < 0.45: reasons.append("muestra pequeña (pocos juegos en la temporada)")
    if odds and odds.get("nv", {}).get("ml"):
        nv = odds["nv"]["ml"]
        gap = abs(model["p_home"] - nv.get("home", model["p_home"]))
        if gap <= 0.08: score += 1
        elif gap > DIVERGENCE_HIGH:
            score -= 1 if gap <= 0.15 else 2
            reasons.append("Divergencia alta (modelo vs mercado s/vig > 10 pp)")
    else:
        reasons.append("sin línea de mercado para contrastar")
        score -= 1
    if flags.get("key_injury"): score -= 1; reasons.append("jugador clave en lista de lesionados")
    if family == "baseball" and not flags.get("pitchers_known"): score -= 1; reasons.append("abridores no confirmados")
    if family in ("tennis",): score = min(score, 0); reasons.append("modelo de tenis simple (sólo ranking, sin superficie/forma)")
    lvl = "Alta" if score >= 3 else ("Media" if score >= 1 else "Baja")
    return dict(level=lvl, emoji={"Alta": "🟢", "Media": "🟡", "Baja": "🔴"}[lvl], score=score, reasons=reasons)

STATUS_META = {
    "PICK": ("🔥", "PICK"), "LEAN": ("🟡", "LEAN LIGERO"), "PASS": ("⛔", "PASS"), "SIN_LINEA": ("🔍", "SIN LÍNEA"),
}

def rank_key(c):
    """Orden: sin divergencia alta primero, luego mayor EV (al precio pagado), luego confianza, luego edge."""
    ev = c.get("ev") if c.get("ev") is not None else -999
    cw = CONF_RANK.get(c.get("conf_level") or "Baja", 0)
    div = 1 if c.get("divergence_high") else 0
    edge = c.get("edge") if c.get("edge") is not None else -99
    return (div, -ev, -cw, -edge)

def decide(cands, model, home_name, away_name):
    """Lean siempre presente. PASS sólo si no hay edge. Orden por EV y confianza, no por edge crudo."""
    out = {"candidates": sorted(cands, key=rank_key)}
    if cands:
        best = out["candidates"][0]
        out["lean"] = best
        out["status"] = best["status"]
    else:
        # sin línea: lean = favorito del modelo
        fav_home = model["p_home"] >= model["p_away"] if model.get("p_draw") is None else (model["p_home"] >= max(model["p_away"], model["p_draw"]))
        side = "home" if fav_home else "away"
        if model.get("p_draw") is not None and model["p_draw"] > max(model["p_home"], model["p_away"]): side = "draw"
        p = {"home": model["p_home"], "away": model["p_away"], "draw": model.get("p_draw")}[side]
        nm = {"home": home_name, "away": away_name, "draw": "Empate"}[side]
        dec_min = (1 + MIN_EV_MARGIN) / p
        out["lean"] = dict(market="ML", side=side, label=f"{nm} ML", price=None, price_txt=None, p_model=p, p_nv=None, p_final=p,
                           edge=None, ev=None, fair=prob_to_am(p), fair_txt=fmt_am(prob_to_am(p)),
                           max_price=prob_to_am(1 / dec_min), max_txt=fmt_am(prob_to_am(1 / dec_min)), status="SIN_LINEA", implied_raw=None)
        out["status"] = "SIN_LINEA"
    return out


def apply_confidence(cands, conf):
    """PICK sólo con confianza Media/Alta. Divergencia alta => REVISAR (no PICK/estrella). Confianza Baja degrada PICK a LEAN."""
    for c in cands:
        c["conf_level"] = conf.get("level")
        if c.get("divergence_high"):
            c["flag"] = "Divergencia alta"
            c["edge_display"] = None
            if c.get("status") in ("PICK", "LEAN"):
                c["status"] = "REVISAR"
                c["downgraded"] = True
                c["downgraded_reason"] = "Divergencia alta"
        else:
            c["edge_display"] = c.get("edge")
            if c["status"] == "PICK" and conf["level"] == "Baja":
                c["status"] = "LEAN"; c["downgraded"] = True
