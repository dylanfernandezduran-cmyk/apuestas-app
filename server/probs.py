"""Sección 'Probabilidades': todos los resultados de cada mercado (ML/1X2, hándicap, total, doble oportunidad)
con probabilidad del modelo, probabilidad sin vig del mercado (consenso y Pinnacle), línea justa, mejor precio y edge.
Todo se deriva de datos reales; si no hay dato, queda None ('Sin dato' en la UI). Nunca se inventan números."""
from .odds import prob_to_am, fmt_am, am_to_dec
from . import model as M

SPREAD_TITLE = {"mlb": "Run line", "nhl": "Puck line", "futbol": "Hándicap", "tenis": "Hándicap de juegos", "nba": "Spread", "nfl": "Spread"}

def _nm(game, side):
    H, A = game["home"], game["away"]
    ten = game.get("sport") == "tenis"
    if side == "home": return H["name"], (None if ten else "local")
    if side == "away": return A["name"], (None if ten else "visitante")
    return {"draw": "Empate", "over": "Over", "under": "Under"}.get(side, side), None

def _label(game, side, line=None):
    n, role = _nm(game, side)
    s = n
    if line is not None and side in ("home", "away"): s += f" {line:+g}"
    if role: s += f" ({role})"
    return s

def _best(books, odds, mkt, side, line):
    """Mejor precio disponible a la MISMA línea. books: lista del comparador; fallback: una sola casa de ESPN."""
    cands = []
    for b in books or []:
        if b["kind"] not in ("book", "sharp"): continue
        if mkt == "ml":
            p = (b.get("ml") or {}).get(side)
            if p is not None: cands.append((p, b["name"]))
        else:
            c = (b.get(mkt) or {}).get(side)
            if c and c.get("line") == line: cands.append((c["price"], b["name"]))
    if cands:
        mx = max(p for p, _ in cands)
        names = [n for p, n in cands if p == mx]
        return dict(price=mx, price_txt=fmt_am(mx), book=" / ".join(names[:3]), n_books=len(cands))
    if odds and not books:
        if mkt == "ml": p = (odds.get("ml") or {}).get(side)
        else:
            c = (odds.get(mkt) or {}).get(side); p = c["price"] if c and c.get("line") == line else None
        if p is not None: return dict(price=p, price_txt=fmt_am(p), book=odds.get("book"), n_books=1)
    return None

def _quarter(x): return x is not None and (x * 4) % 2 != 0

def _unit(odds_total_line, spread_line):
    if odds_total_line is not None: return "sets" if odds_total_line < 6 else "juegos"
    if spread_line is not None: return "sets" if abs(spread_line) <= 2.5 else "juegos"
    return None

def build(game, mdl, odds, mk, w=None):
    sport = game.get("sport"); soccer = sport == "futbol"
    books = (mk or {}).get("books") or []
    cons = (mk or {}).get("consensus_nv") or {}
    pin = (mk or {}).get("sharp_nv") or {}
    ref = (mk or {}).get("ref") or {}
    onv = (odds or {}).get("nv") or {}
    if w is None: w = M.blend_weight(mdl) if mdl else 0.0
    markets = []; notes = []

    def outcome(mkt, side, line, p_model, p_cons, cons_src, p_pin, pin_line, p_push=None, model_note=None):
        best = _best(books, odds, mkt, side, line)
        p_ref = p_cons if p_cons is not None else (p_pin if (p_pin is not None and (pin_line is None or pin_line == line)) else None)
        o = dict(key=f"{mkt}.{side}", market=mkt, side=side, name=_nm(game, side)[0], role=_nm(game, side)[1], label=_label(game, side, line if mkt in ("spread", "sspread") else None),
                 line=line, p_model=None, p_model_raw=p_model, clipped=False, p_final=None, p_nv=p_cons, nv_src=cons_src, p_pin=p_pin, pin_line=pin_line,
                 fair_txt=None, fair_nv_txt=fmt_am(prob_to_am(p_cons)) if p_cons else None, best=best, edge=None, ev=None, p_push=p_push, model_note=model_note)
        if p_model is not None:
            price = best["price"] if best else None
            c = M._cand(mkt, side, o["label"], price, p_model, p_ref, w, line=line)
            o.update(p_model=c["p_model"], clipped=c["clipped"], p_final=c["p_final"], fair_txt=c["fair_txt"], edge=c["edge"], ev=c["ev"])
        return o

    # ---------------- ML / 1X2
    tennis = sport == "tenis"
    ml_sides = ["home", "draw", "away"] if (not tennis and (soccer or (odds or {}).get("ml", {}).get("draw") is not None or cons.get("ml", {}).get("draw") is not None)) else ["home", "away"]
    pm = {"home": (mdl or {}).get("p_home"), "draw": (mdl or {}).get("p_draw"), "away": (mdl or {}).get("p_away")}
    cml = cons.get("ml") or {}; pml = pin.get("ml") or {}
    if cml: csrc = f"Consenso ({cml.get('n', '?')} casas)"
    elif onv.get("ml"): csrc = f"{(odds or {}).get('book', 'casa')} (una sola casa)"
    else: csrc = None
    cml = cml or onv.get("ml") or {}
    has_ml_mkt = any(s in cml or s in pml for s in ml_sides)
    if has_ml_mkt or any(pm[s] is not None for s in ml_sides):
        outs = [outcome("ml", s, None, pm[s] if (s != "draw" or soccer) else None, cml.get(s), csrc, pml.get(s), None) for s in ml_sides]
        markets.append(dict(key="ml", title="Ganador (1X2)" if "draw" in ml_sides else "Ganador (moneyline)", outcomes=outs, unit=None))
        # doble oportunidad (derivada del 1X2)
        if soccer and "draw" in ml_sides:
            def comb(a, b, d):
                pmv = (pm[a] + pm[b]) if (pm[a] is not None and pm[b] is not None) else None
                pc = (d.get(a) + d.get(b)) if (a in d and b in d) else None
                return pmv, pc
            dcs = []
            for key, a, b, name in (("1X", "home", "draw", f"{game['home']['name']} o Empate"), ("X2", "away", "draw", f"{game['away']['name']} o Empate"), ("12", "home", "away", f"{game['home']['name']} o {game['away']['name']} (sin empate)")):
                pmv, pc = comb(a, b, cml); _, pp = comb(a, b, pml)
                o = outcome("dc", key, None, pmv, pc, csrc, pp, None)
                o["name"] = name; o["role"] = None; o["label"] = name; o["best"] = None
                o["model_note"] = "Derivado del 1X2 (suma de probabilidades); sin precio directo de doble oportunidad"
                dcs.append(o)
            markets.append(dict(key="dc", title="Doble oportunidad", outcomes=dcs, unit=None, derived=True))

    # ---------------- Hándicap
    sp_lines = {"home": ((odds or {}).get("spread") or {}).get("home"), "away": ((odds or {}).get("spread") or {}).get("away")}
    L = ref.get("spread_home")
    if L is None and sp_lines["home"]: L = sp_lines["home"]["line"]
    if L is None and (pin.get("spread") or {}).get("line") is not None: L = pin["spread"]["line"]
    tot_line = ref.get("total")
    if tot_line is None and ((odds or {}).get("total") or {}).get("over"): tot_line = odds["total"]["over"]["line"]
    if tot_line is None and (pin.get("total") or {}).get("line") is not None: tot_line = pin["total"]["line"]
    if L is not None:
        cs = cons.get("spread"); ps = pin.get("spread")
        if cs and cs.get("line") == L: pc = {"home": cs["home"], "away": cs["away"]}; csrc2 = f"Consenso ({cs.get('n', '?')} casas)"
        elif onv.get("spread") and sp_lines["home"] and sp_lines["home"]["line"] == L: pc = onv["spread"]; csrc2 = f"{(odds or {}).get('book', 'casa')} (una sola casa)"
        else: pc = {}; csrc2 = None
        pp = {}; ppl = None
        if ps: pp = {"home": ps["home"], "away": ps["away"]}; ppl = ps["line"]
        pmh = pma = push = None; mnote = None
        if mdl and "cover" in mdl:
            if _quarter(L): mnote = "Línea de cuarto (asiática): el modelo no la evalúa"
            else:
                w_, l_, push = mdl["cover"](-L); pmh = w_
                pma = mdl["cover"](-L)[1]   # visitante cubre si margen local < -L
        elif mdl: mnote = "El modelo no estima márgenes para este deporte"
        outs = []
        for s, ln in (("home", L), ("away", -L)):
            o = outcome("spread", s, ln, pmh if s == "home" else pma, pc.get(s), csrc2, pp.get(s), (ppl if s == "home" else (-ppl if ppl is not None else None)),
                        p_push=(push if (push and float(L).is_integer()) else None), model_note=mnote)
            if o["p_pin"] is not None and o["pin_line"] is not None and o["pin_line"] != ln: o["p_pin_diff_line"] = True
            outs.append(o)
        unit = "juegos" if tennis else None   # en tenis spread/total del app = JUEGOS (los de sets van aparte: sspread/stotal)
        if tennis:
            for o in outs: o["label"] = f"{o['label']} juegos"
        markets.append(dict(key="spread", title=SPREAD_TITLE.get(sport, "Hándicap"), outcomes=outs, unit=unit))
    # ---------------- Total
    if tot_line is not None:
        ct = cons.get("total"); pt = pin.get("total")
        if ct and ct.get("line") == tot_line: pc = ct; csrc3 = f"Consenso ({ct.get('n', '?')} casas)"
        elif onv.get("total") and ((odds or {}).get("total") or {}).get("over", {}).get("line") == tot_line: pc = onv["total"]; csrc3 = f"{(odds or {}).get('book', 'casa')} (una sola casa)"
        else: pc = {}; csrc3 = None
        pp = {}; ppl = None
        if pt: pp = dict(over=pt["over"], under=pt["under"]); ppl = pt["line"]
        pmo = pmu = push = None; mnote = None
        if mdl and "total" in mdl:
            if _quarter(tot_line): mnote = "Línea de cuarto (asiática): el modelo no la evalúa"
            else:
                pmo, pmu, push = mdl["total"](tot_line)
        elif mdl: mnote = "El modelo no estima totales para este deporte"
        outs = [outcome("total", s, tot_line, pmo if s == "over" else pmu, pc.get(s), csrc3, pp.get(s), ppl,
                        p_push=(push if (push and float(tot_line).is_integer()) else None), model_note=mnote) for s in ("over", "under")]
        for o in outs: o["label"] = f"{'Over' if o['side'] == 'over' else 'Under'} {tot_line:g}" + (" juegos" if tennis else "")
        unit = "juegos" if tennis else None
        markets.append(dict(key="total", title="Total de juegos" if tennis else "Total (más/menos)", outcomes=outs, unit=unit))
    # ---------------- Tenis: hándicap y total de SETS (Pinnacle)
    if tennis:
        pb = next((b for b in books if b["kind"] == "sharp"), None) or {}
        pnv = pin
        for key, title, sides in (("sspread", "Hándicap de sets", ("home", "away")), ("stotal", "Total de sets", ("over", "under"))):
            cell = pb.get(key) or {}
            nvv = pnv.get(key)
            if not nvv or not all(sd in cell for sd in sides): continue
            ln = nvv["line"]
            if key == "sspread":
                outs = []
                for sd, l_ in (("home", ln), ("away", -ln)):
                    o = outcome("sspread", sd, l_, None, None, None, nvv.get(sd), l_, model_note="El modelo no estima sets")
                    o["label"] = f"{o['label']} sets"; outs.append(o)
            else:
                outs = []
                for sd in sides:
                    o = outcome("stotal", sd, ln, None, None, None, nvv.get(sd), ln, model_note="El modelo no estima sets")
                    o["label"] = f"{'Over' if sd == 'over' else 'Under'} {ln:g} sets"; outs.append(o)
            markets.append(dict(key=key, title=title, outcomes=outs, unit="sets"))
    if tennis:
        notes.append("Tenis: el modelo (logística sobre puntos de ranking) sólo estima el ganador; hándicap y total de juegos, y hándicap y total de sets, son sólo mercado (Pinnacle; 'Modelo: Sin dato'). No hay empate, 1X2 ni doble oportunidad en tenis.")
    if mdl is None: notes.append("Modelo: Sin dato (no hay suficientes resultados/ranking de alguno de los participantes); se muestran sólo probabilidades de mercado.")
    elif mdl.get("kind") == "margen": notes.append("Modelo de margen: normal(margen esperado, σ de la liga) con corrección de continuidad; el total usa normal(total esperado, σ). Push excluido y renormalizado.")
    elif mdl.get("kind") == "poisson": notes.append("Modelo Poisson de goles (ataque/defensa suavizados): de la matriz de marcadores salen 1X2, hándicap, totales y doble oportunidad.")
    if not books and not odds: notes.append("Mercado: Sin dato (ninguna fuente publica línea para este juego).")
    return dict(markets=markets, notes=notes, w_model=(w if mdl else None), ref=dict(spread_home=L, total=tot_line), model_ok=bool(mdl))

def brief(probs):
    """Mejor resultado por mercado (ML, hándicap, total): mayor edge; si no hay edge, mayor probabilidad del modelo; si no hay modelo, mayor prob. de mercado."""
    out = []
    for m in (probs or {}).get("markets", []):
        if m["key"] == "dc": continue
        os_ = m["outcomes"]
        pool = [o for o in os_ if o["edge"] is not None]
        if pool: b = max(pool, key=lambda o: o["edge"])
        else:
            pool = [o for o in os_ if o["p_model"] is not None]
            if pool: b = max(pool, key=lambda o: o["p_model"])
            else:
                pool = [o for o in os_ if o["p_nv"] is not None] or [o for o in os_ if o["p_pin"] is not None]
                if not pool: continue
                b = max(pool, key=lambda o: o["p_nv"] if o["p_nv"] is not None else o["p_pin"])
        out.append(dict(market=m["key"], title=m["title"], key=b["key"], side=b["side"], line=b.get("line"), unit=m.get("unit"), label=b["label"], p_model=b["p_model"], p_final=b["p_final"], p_nv=b["p_nv"] if b["p_nv"] is not None else b["p_pin"],
                        edge=b["edge"], best=b["best"], clipped=b["clipped"]))
    return out
