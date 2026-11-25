"""Tablero «Picks NRNM» de la pantalla principal.

Sólo picks registrados que coinciden con la Predicción NRNM (mismo mercado, lado y línea).
Todas las cifras de cada pick salen de los MISMOS dos números: la cuota registrada (actual)
y la probabilidad final del modelo (p_final). De ahí:
  implícita = 1 / decimal(cuota)            (con vig, la que realmente pagas)
  ventaja   = p_final − implícita            (pp; mismo signo que el EV)
  EV        = p_final × decimal − 1          (%)
Nada se inventa: sin cuota o sin p_final no es pick.
"""
from __future__ import annotations
import json
import time

from .odds import am_to_dec, fmt_am
from . import consistency as CS

DIV_PP = 10.0           # divergencia alta: |modelo crudo − mercado sin vig| > 10 pp
MIN_EV = 0.0            # sólo EV > 0 es «pick con valor»
CONF_RANK = {"Alta": 3, "Media": 2, "Baja": 1}
DONE = ("GANADO", "PERDIDO", "PUSH", "MEDIO_GANADO", "MEDIO_PERDIDO")
MK_ES = {"ml": "Ganador", "spread": "Hándicap", "total": "Total", "btts": "Ambos anotan",
         "sspread": "Hándicap sets", "stotal": "Total sets"}
SPORT_ES = {"nba": "NBA", "nfl": "NFL", "nhl": "NHL", "mlb": "MLB", "futbol": "Fútbol", "tenis": "Tenis"}

_cache = {}


def _f(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def metrics(odds, p_final, p_nv=None, p_model=None):
    """Métricas coherentes de un pick a partir de cuota y p_final. None si falta algo."""
    try:
        o = int(odds)
    except (TypeError, ValueError):
        return None
    p = _f(p_final)
    if p is None or not (0 < p < 1) or o == 0:
        return None
    dec = am_to_dec(o)
    imp = 1.0 / dec
    pnv, pm = _f(p_nv), _f(p_model)
    div = abs(pm - pnv) * 100 if (pm is not None and pnv is not None) else None
    return dict(
        odds=o, odds_txt=fmt_am(o), dec=round(dec, 3),
        p_final=round(p * 100, 1), p_implied=round(imp * 100, 1),
        p_fair=(round(pnv * 100, 1) if pnv is not None else None),
        p_model=(round(pm * 100, 1) if pm is not None else None),
        edge_pp=round((p - imp) * 100, 1),
        ev_pct=round((p * dec - 1) * 100, 1),
        divergence_pp=(round(div, 1) if div is not None else None),
        divergence_high=bool(div is not None and div > DIV_PP),
    )


def _published(row):
    try:
        w = json.loads(row.get("why_json") or "null") or {}
        return w.get("published"), w.get("reason")
    except Exception:
        return None, None


def _conf(row, ev_pct, div_high):
    lvl = row.get("conf_level")
    if ev_pct is None or ev_pct <= 0 or div_high or lvl not in CONF_RANK:
        return "no aplica" if (ev_pct is None or ev_pct <= 0 or div_high) else (lvl or "sin dato")
    return lvl


def _moves(row):
    try:
        mv = json.loads(row.get("moves") or "[]") or []
    except Exception:
        mv = []
    return len(mv)


def _item(row, now):
    m = metrics(row.get("odds"), row.get("p_final"), row.get("p_nv"), row.get("p_model"))
    if not m:
        return None
    sport = row.get("sport")
    pub, why = _published(row)
    started = int(row.get("start_ts") or 0) <= now
    conf = _conf(row, m["ev_pct"], m["divergence_high"])
    ol, oo = row.get("open_line"), row.get("open_odds")
    return dict(
        id=row.get("id"), sport=sport, sport_name=SPORT_ES.get(sport, sport), league=row.get("league"),
        eid=str(row.get("eid")), home=row.get("home"), away=row.get("away"),
        game=CS._game_title(row.get("home"), row.get("away"), sport),
        kickoff_ts=row.get("start_ts"), kickoff_cdmx=CS._kickoff_cdmx(row.get("start_ts")), live=started,
        type=row.get("type") or "suggestion", market=row.get("market"), market_name=MK_ES.get(row.get("market"), row.get("market")),
        selection=row.get("selection"), line=row.get("line"), pick=row.get("label"), book=row.get("book"),
        open_line=ol, open_odds=oo, open_odds_txt=fmt_am(int(oo)) if oo is not None else None,
        line_moved=(ol is not None and row.get("line") is not None and abs(float(ol) - float(row["line"])) > 1e-9),
        odds_moved=(oo is not None and int(oo) != m["odds"]), n_moves=_moves(row),
        confidence=conf, published=pub, filter_reason=why,
        value=bool(m["ev_pct"] > MIN_EV and not m["divergence_high"]),
        signals=CS._signals_brief(row),
        href=f"#/juego/{row.get('league')}/{row.get('eid')}",
        **m,
    )


def _key(it):
    return (
        0 if it["value"] else 1,
        1 if it["divergence_high"] else 0,
        -(it["ev_pct"] or 0) - 0.5 * CONF_RANK.get(it["confidence"], 0),
        -CONF_RANK.get(it["confidence"], 0),
        it.get("kickoff_ts") or 0,
    )


def _agg(rows):
    W = L = P = 0.0
    units = 0.0; npr = 0; clvs = []
    from . import record as REC
    nun = 0
    for r in rows:
        s = r["status"]
        if r.get("odds") is None:      # sin cuota no es pick: fuera de acierto y ROI (misma muestra)
            nun += 1; continue
        if s == "GANADO": W += 1
        elif s == "PERDIDO": L += 1
        elif s == "PUSH": P += 1
        elif s == "MEDIO_GANADO": W += .5; P += .5
        elif s == "MEDIO_PERDIDO": L += .5; P += .5
        u = REC.profit(s, r["odds"])
        if u is not None:
            units += u; npr += 1
        v = REC.clv_pct(r.get("open_odds"), r.get("odds"))
        if v is not None: clvs.append(v)
    return dict(W=W, L=L, P=P, n=len(rows) - nun, n_unpriced=nun,
                hit_pct=(round(W / (W + L) * 100, 1) if W + L else None),
                units=(round(units, 2) if npr else None), n_priced=npr,
                roi=(round(units / npr * 100, 1) if npr else None),
                clv_avg=(round(sum(clvs) / len(clvs), 2) if clvs else None), clv_n=len(clvs))


def calibration(rows):
    """Brier y log loss de p_final (y del mercado sin vig p_nv como referencia) en picks calificados G/P con cuota.
    Hit%, ROI y n por deporte y por mercado. Sólo datos reales del récord."""
    import math
    from . import record as REC
    def blank():
        return dict(n=0, b=0.0, ll=0.0, bm=0.0, nm=0, W=0, L=0, u=0.0)
    tot, by_s, by_m = blank(), {}, {}
    for r in rows:
        s = r["status"]
        if s not in ("GANADO", "PERDIDO") or r.get("odds") is None:
            continue
        p = _f(r.get("p_final"))
        y = 1.0 if s == "GANADO" else 0.0
        u = REC.profit(s, r["odds"]) or 0.0
        for acc in (tot, by_s.setdefault(r.get("sport") or "?", blank()), by_m.setdefault(r.get("market") or "?", blank())):
            acc["W"] += int(y); acc["L"] += int(1 - y); acc["u"] += u
            if p is not None and 0 < p < 1:
                acc["n"] += 1; acc["b"] += (p - y) ** 2
                pc = min(max(p, 1e-6), 1 - 1e-6); acc["ll"] += -(y * math.log(pc) + (1 - y) * math.log(1 - pc))
                q = _f(r.get("p_nv"))
                if q is not None and 0 < q < 1:
                    acc["nm"] += 1; acc["bm"] += (q - y) ** 2
    def out(a, label=None):
        n = a["W"] + a["L"]
        return dict(label=label, n=n, W=a["W"], L=a["L"],
                    hit_pct=(round(a["W"] / n * 100, 1) if n else None),
                    roi=(round(a["u"] / n * 100, 1) if n else None),
                    brier=(round(a["b"] / a["n"], 4) if a["n"] else None),
                    logloss=(round(a["ll"] / a["n"], 4) if a["n"] else None),
                    brier_market=(round(a["bm"] / a["nm"], 4) if a["nm"] else None))
    # calibración por cubeta de probabilidad predicha (p_final del lado apostado) vs acierto real
    edges = [(0.0, 0.5, "<50%"), (0.5, 0.6, "50–60%"), (0.6, 0.7, "60–70%"), (0.7, 0.8, "70–80%"), (0.8, 0.9, "80–90%"), (0.9, 1.01, "≥90%")]
    bk = {lab: dict(n=0, W=0, sp=0.0, sq=0.0, u=0.0) for _, _, lab in edges}
    for r in rows:
        s = r["status"]
        p = _f(r.get("p_final"))
        if s not in ("GANADO", "PERDIDO") or r.get("odds") is None or p is None:
            continue
        lab = next(l for a, b, l in edges if a <= p < b)
        x = bk[lab]; x["n"] += 1; x["W"] += (s == "GANADO"); x["sp"] += p
        q = _f(r.get("p_nv")); x["sq"] += (q if q is not None else p)
        x["u"] += REC.profit(s, r["odds"]) or 0.0
    buckets = []
    for _, _, lab in edges:
        x = bk[lab]
        if not x["n"]:
            continue
        pred, real, mkt = x["sp"] / x["n"] * 100, x["W"] / x["n"] * 100, x["sq"] / x["n"] * 100
        buckets.append(dict(label=lab, n=x["n"], pred=round(pred, 1), real=round(real, 1), market=round(mkt, 1),
                            gap=round(real - pred, 1), roi=round(x["u"] / x["n"] * 100, 1)))
    return dict(overall=out(tot, "Total"), buckets=buckets,
                by_sport=[out(v, SPORT_ES.get(k, k)) for k, v in sorted(by_s.items(), key=lambda kv: -(kv[1]["W"] + kv[1]["L"]))],
                by_market=[out(v, MK_ES.get(k, k)) for k, v in sorted(by_m.items(), key=lambda kv: -(kv[1]["W"] + kv[1]["L"]))],
                note="Brier: 0 = perfecto, 0.25 = moneda al aire. Si el Brier del modelo es mayor que el del mercado sin vig, el mercado predice mejor.")


def monthly(rows, fmt="%Y-%m"):
    """Serie mensual (hora CDMX) de picks calificados con cuota: G-P-E, acierto, unidades y ROI. Sólo datos reales."""
    from datetime import datetime, timedelta, timezone
    from . import record as REC
    tz = timezone(timedelta(hours=-6))
    out = {}
    for r in rows:
        s = r["status"]
        if r.get("odds") is None or not r.get("start_ts"):
            continue
        k = datetime.fromtimestamp(int(r["start_ts"]), tz).strftime(fmt)
        a = out.setdefault(k, dict(month=k, W=0, L=0, P=0, u=0.0))
        if s in ("GANADO", "MEDIO_GANADO"): a["W"] += 1
        elif s in ("PERDIDO", "MEDIO_PERDIDO"): a["L"] += 1
        else: a["P"] += 1
        a["u"] += REC.profit(s, r["odds"]) or 0.0
    res = []
    for k in sorted(out):
        a = out[k]; n = a["W"] + a["L"] + a["P"]; d = a["W"] + a["L"]
        res.append(dict(month=k, day=k if fmt != "%Y-%m" else None, n=n, W=a["W"], L=a["L"], P=a["P"], hit=round(100 * a["W"] / d, 1) if d else None,
                        units=round(a["u"], 2), roi=round(100 * a["u"] / n, 1) if n else None))
    return res


def parlays():
    """Tickets (parlays en papel) calificados. Vacío si no hay muestra."""
    try:
        rs = CS._rows("SELECT status, units, dec FROM tickets WHERE status IN ('GANADO','PERDIDO','PUSH')")
    except Exception:
        return None
    if not rs: return dict(n=0)
    W = sum(1 for r in rs if r["status"] == "GANADO"); L = sum(1 for r in rs if r["status"] == "PERDIDO")
    u = sum((r.get("units") or 0.0) for r in rs)
    return dict(n=len(rs), W=W, L=L, hit=round(100 * W / (W + L), 1) if W + L else None, units=round(u, 2), roi=round(100 * u / len(rs), 1))


def record_coincident():
    """Récord real de picks registrados que coincidían con la predicción guardada del juego (pick vigente al inicio)."""
    rows = CS._rows("SELECT * FROM picks WHERE status IN ('GANADO','PERDIDO','PUSH','MEDIO_GANADO','MEDIO_PERDIDO')")
    cache = {}
    ok, ok_val, mains = [], [], []
    for r in rows:
        if r.get("type") == "main":
            mains.append(r)
        pred = CS._load_pred(r["league"], r["eid"], cache)
        if not pred or CS.classify_pick(pred, r)[0] != "ok":
            continue
        ok.append(r)
        m = metrics(r.get("odds"), r.get("p_final"), r.get("p_nv"), r.get("p_model"))
        if m and m["ev_pct"] > MIN_EV and not m["divergence_high"]:
            ok_val.append(r)
    last = sorted(ok, key=lambda r: r.get("start_ts") or 0)[-10:]
    streak = "".join("G" if r["status"] in ("GANADO", "MEDIO_GANADO") else "P" if r["status"] in ("PERDIDO", "MEDIO_PERDIDO") else "E" for r in last)
    return dict(coincident=_agg(ok), coincident_value=_agg(ok_val), main=_agg(mains), last10=streak,
                calibration=calibration(rows), monthly=monthly(rows), daily=monthly(rows, "%Y-%m-%d")[-45:], parlays=parlays(),
                note="Récord real calificado con el marcador final. CLV = cuota de apertura vs cuota vigente al inicio. Unidades a 1u por pick.")


def board(now=None, date=None):
    now = int(now or time.time())
    ck = (date, now // 60)
    if ck in _cache:
        return _cache[ck]
    lo, hi, day = CS.day_window(date, now)
    try:
        CS._load_pred("_", "_")
    except Exception:
        pass
    rows = CS._rows("SELECT * FROM picks WHERE status='PENDIENTE' AND start_ts>=? AND start_ts<? ORDER BY start_ts", (lo, hi))
    from . import policy as POL
    H = POL.history(CS._rows)
    cache, items, n_reg, n_mis, mism = {}, [], len(rows), 0, []
    for r in rows:
        pred = CS._load_pred(r["league"], r["eid"], cache)
        if not pred:
            continue
        kind, why = CS.classify_pick(pred, r)
        if kind == "mismatch":
            n_mis += 1
            tgt = CS.pred_target(pred, r.get("market"), r.get("selection")) or {}
            mism.append(dict(game=CS._game_title(r.get("home"), r.get("away"), r.get("sport")), sport=SPORT_ES.get(r.get("sport"), r.get("sport")),
                             registered=r.get("label"), registered_at=r.get("created_at"), open_line=r.get("open_line"), line=r.get("line"),
                             reason=why, prediction=tgt.get("label") or (f"{tgt.get('side')} {tgt.get('line') if tgt.get('line') is not None else ''}".strip()),
                             live=int(r.get("start_ts") or 0) <= now,
                             explain=("La línea se movió desde que se registró" if why == "línea" else "La predicción cambió de lado (línea, lesiones o noticias nuevas)") +
                                     ("; el juego ya empezó: se califica el pick vigente al inicio." if int(r.get("start_ts") or 0) <= now else "; antes del inicio se realinea en el siguiente refresco."),
                             href=f"#/juego/{r.get('league')}/{r.get('eid')}"))
        if kind != "ok":
            continue
        it = _item(r, now)
        if it:
            from . import validation as VAL
            vv = VAL.LAST.get((r["league"], str(r["eid"])))
            if vv:
                it["data_quality"] = vv["dq"]["score"]; it["dq_missing"] = vv["dq"]["missing"]
                # el estado se valida sobre el pick del análisis; si este pick no es ese, se valida con sus propias cifras
                st = vv["validation"]["state"] if vv.get("lean") == it["pick"] else None
                it["validation"] = st
                it["validation_reasons"] = vv["validation"]["reasons"] if st else []
            if not it.get("validation"):
                it["validation"] = "PASAR" if it["ev_pct"] <= 0 else ("INCIERTO" if it["divergence_high"] or it["confidence"] not in ("Alta", "Media") else "VALIDADO")
                it.setdefault("validation_reasons", ["EV ≤ 0 (sin valor)"] if it["ev_pct"] <= 0 else [])
            pol = POL.check(it, H, now=now, consistent=True, dq=it.get("data_quality"), updated_at=r.get("updated_at") or r.get("created_at"))
            it["tier"] = pol["tier"]; it["locks"] = pol["locks"]; it["approved"] = pol["approved"]
            if not pol["approved"] and it.get("validation") == "VALIDADO":
                it["validation"] = "INCIERTO"; it["validation_reasons"] = [l["reason"] for l in pol["locks"]]
            items.append(it)
    items.sort(key=_key)
    # recomendaciones = sólo los que pasan TODOS los candados; el resto queda registrado y se califica (auditoría)
    val = [i for i in items if i["approved"]]
    blocked = [i for i in items if not i["approved"] and i["value"]]
    rest = [i for i in items if not i["approved"] and not i["value"]]
    try:
        rec = record_coincident()
    except Exception as e:
        rec = dict(error=type(e).__name__)
    res = dict(date=day, now=now, n_registered=n_reg, n_mismatch=n_mis, n_coincident=len(items),
               n=len(val), items=val, blocked=blocked, no_value=rest, policy=POL.config(), mismatches=mism, record=rec,
               formula="Ventaja = Prob. NRNM − implícita de la cuota. EV = Prob. NRNM × cuota decimal − 1. Mismos números, mismo signo.",
               note=CS.AGREE_NOTE)
    _cache.clear(); _cache[ck] = res
    return res
