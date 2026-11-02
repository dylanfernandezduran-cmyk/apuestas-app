"""Utilidades de momios: americano <-> decimal <-> probabilidad, quitar vig."""
import math

def parse_am(v):
    """'+150' / '-110' / 'EVEN' / 150 -> int, None si no es válido ('OFF', '', None)."""
    if v is None: return None
    if isinstance(v, (int, float)):
        return int(v) if v != 0 else None
    s = str(v).strip().upper().replace("−", "-")
    if s in ("EVEN", "EV", "PK"): return 100
    try:
        return int(float(s))
    except Exception:
        return None

def am_to_dec(a):
    return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)

def am_to_prob(a):
    return 100 / (a + 100) if a > 0 else abs(a) / (abs(a) + 100)

def prob_to_am(p):
    if p is None or p <= 0 or p >= 1: return None
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)

def fmt_am(a):
    if a is None: return None
    return f"+{a}" if a > 0 else str(a)

def devig(probs):
    """Normalización proporcional (multiplicativa). probs: lista de prob. implícitas con vig."""
    s = sum(probs)
    return [p / s for p in probs], s - 1  # prob sin vig, overround

def parse_line(s):
    """'o46.5' / 'u46.5' / '-3' / '+0.5' -> float"""
    if s is None: return None
    try:
        return float(str(s).strip().lower().lstrip("ou").replace("+", ""))
    except Exception:
        return None

def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def extract_odds(oc):
    """Extrae mercados de un objeto 'odds'/'pickcenter' de ESPN (DraftKings). Usa 'close' (línea vigente antes del juego).
    Devuelve dict o None."""
    if not oc: return None
    prov = (oc.get("provider") or {}).get("displayName") or (oc.get("provider") or {}).get("name") or "Casa"
    out = {"book": prov, "ml": {}, "spread": {}, "total": {}, "open": {}}

    def cur(node, prefer=("close", "current")):
        if not node: return None
        for k in prefer:
            if k in node and node[k]: return node[k]
        return None

    ml = oc.get("moneyline") or {}
    for side in ("home", "away", "draw"):
        n = cur(ml.get(side))
        v = parse_am(n.get("odds")) if n else None
        if v is None:
            node = oc.get(f"{side}TeamOdds") if side != "draw" else oc.get("drawOdds")
            if node: v = parse_am(node.get("moneyLine"))
        if v is not None: out["ml"][side] = v
        o = (ml.get(side) or {}).get("open")
        if o and parse_am(o.get("odds")) is not None:
            out["open"].setdefault("ml", {})[side] = parse_am(o.get("odds"))

    ps = oc.get("pointSpread") or {}
    for side in ("home", "away"):
        n = cur(ps.get(side))
        line = parse_line(n.get("line")) if n else None
        price = parse_am(n.get("odds")) if n else None
        if line is None or price is None:
            node = oc.get(f"{side}TeamOdds") or {}
            sp = oc.get("spread")
            if price is None: price = parse_am(node.get("spreadOdds"))
            if line is None and sp is not None:
                is_fav = node.get("favorite")
                if is_fav is not None:
                    line = -abs(sp) if is_fav else abs(sp)
                else:
                    line = sp if side == "home" else -sp
        if line is not None and price is not None:
            out["spread"][side] = {"line": line, "price": price}

    tt = oc.get("total") or {}
    for side, key in (("over", "over"), ("under", "under")):
        n = cur(tt.get(key))
        line = parse_line(n.get("line")) if n else None
        price = parse_am(n.get("odds")) if n else None
        if line is None: line = oc.get("overUnder")
        if price is None: price = parse_am(oc.get(f"{key}Odds"))
        if line is not None and price is not None:
            out["total"][side] = {"line": float(line), "price": price}

    if not (out["ml"] or out["spread"] or out["total"]): return None

    # probabilidades sin vig
    nv = {}
    ml_sides = [s for s in ("home", "draw", "away") if s in out["ml"]]
    if len(ml_sides) >= 2:
        ps_, ov = devig([am_to_prob(out["ml"][s]) for s in ml_sides])
        nv["ml"] = {s: p for s, p in zip(ml_sides, ps_)}; nv["ml_vig"] = ov
    if "home" in out["spread"] and "away" in out["spread"]:
        ps_, ov = devig([am_to_prob(out["spread"]["home"]["price"]), am_to_prob(out["spread"]["away"]["price"])])
        nv["spread"] = {"home": ps_[0], "away": ps_[1]}; nv["spread_vig"] = ov
    if "over" in out["total"] and "under" in out["total"]:
        ps_, ov = devig([am_to_prob(out["total"]["over"]["price"]), am_to_prob(out["total"]["under"]["price"])])
        nv["total"] = {"over": ps_[0], "under": ps_[1]}; nv["total_vig"] = ov
    out["nv"] = nv
    return out
