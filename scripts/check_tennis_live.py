"""Verificación en vivo (servidor corriendo en :8765): en TODOS los partidos de tenis con mercado, el favorito del ML lleva el hándicap
negativo (juegos y sets), las unidades dicen juegos/sets, y no hay empate/1X2/doble oportunidad."""
import json, sys, urllib.request
B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
j = lambda p: json.load(urllib.request.urlopen(B + p, timeout=180))
n = bad = 0
for lg in ("atp", "wta"):
    for g in j(f"/api/games?league={lg}")["games"]:
        if g["state"] != "pre": continue
        d = j(f"/api/game/{lg}/{g['id']}")
        m = {x["key"]: x for x in d["probs"]["markets"]}
        if "spread" not in m or "ml" not in m: continue
        n += 1
        errs = []
        if "dc" in m or any(o["side"] == "draw" for o in m["ml"]["outcomes"]): errs.append("hay empate/dc")
        ml = {o["side"]: (o["p_nv"] if o["p_nv"] is not None else o["p_pin"]) for o in m["ml"]["outcomes"]}
        if abs((ml.get("home") or 0) - (ml.get("away") or 0)) < 0.03: continue    # pick'em: no hay favorito claro
        fav = "home" if (ml.get("home") or 0) >= (ml.get("away") or 0) else "away"
        for k, unit in (("spread", "juegos"), ("sspread", "sets")):
            if k not in m: continue
            if m[k]["unit"] != unit: errs.append(f"{k} unidad {m[k]['unit']}")
            o = next(o for o in m[k]["outcomes"] if o["side"] == fav)
            if o["line"] > 0: errs.append(f"favorito {fav} con {k} positivo {o['line']}")
            if unit not in o["label"]: errs.append(f"label sin unidad: {o['label']}")
        for k, unit in (("total", "juegos"), ("stotal", "sets")):
            if k in m and (m[k]["unit"] != unit or unit not in m[k]["outcomes"][0]["label"]): errs.append(f"{k} unidad")
        tl = m["total"]["outcomes"][0]["line"] if "total" in m else None
        if tl is not None and tl < 12: errs.append(f"total de juegos con línea {tl} (¿sets?)")
        if errs: bad += 1; print("MAL", lg, g["id"], g["away"]["name"], "@", g["home"]["name"], errs)
print(f"partidos revisados: {n} · con problemas: {bad}")
sys.exit(1 if bad else 0)
