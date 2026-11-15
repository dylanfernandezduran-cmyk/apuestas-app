"""Aprendizaje conservador a partir del récord real.

Segmenta picks ya calificados (deporte, mercado, lado, banda de cuota/EV, confianza),
calcula acierto, ROI y CLV con n e intervalos, y decide bloqueos o umbrales más
estrictos. Nunca inventa cifras: si un dato no está, el segmento o la señal se omite.
No se relajan umbrales en segmentos positivos (evita sobreajuste).
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict

from . import history
from .odds import am_to_dec
from .record import clv_pct

DONE = ("GANADO", "PERDIDO", "PUSH", "MEDIO_GANADO", "MEDIO_PERDIDO")
MIN_N = 30
PRIOR_N = 40
# intervalo de confianza (aprox. 95 %)
Z = 1.96

# mercado canónico
MKT_CANON = {
    "ml": "ml", "ML": "ml",
    "spread": "spread", "Spread": "spread", "sspread": "spread",
    "total": "total", "Total": "total", "OU": "total", "stotal": "total",
    "btts": "btts", "BTTS": "btts",
}


def ev_of(row):
    """EV en porcentaje. Usa el guardado; si falta, se reconstruye con p_final y cuota (nada inventado)."""
    ev = row.get("ev")
    if ev is not None:
        try:
            ev = float(ev)
            return ev * 100.0 if abs(ev) <= 1.0 else ev
        except (TypeError, ValueError):
            pass
    pf, odds = row.get("p_final"), row.get("odds")
    if pf is None or odds is None:
        return None
    try:
        return (float(pf) * am_to_dec(int(odds)) - 1.0) * 100.0
    except Exception:
        return None


def units_of(row):
    if row.get("units") is not None:
        try:
            return float(row["units"])
        except (TypeError, ValueError):
            pass
    st, odds = row.get("status"), row.get("odds")
    if st not in DONE or odds is None:
        return 0.0 if st == "PUSH" else None
    try:
        profit = am_to_dec(int(odds)) - 1.0
    except Exception:
        return None
    if st == "GANADO":
        return profit
    if st == "PERDIDO":
        return -1.0
    if st == "MEDIO_GANADO":
        return profit / 2.0
    if st == "MEDIO_PERDIDO":
        return -0.5
    return 0.0


def wilson(k, n, z=Z):
    """Intervalo de Wilson para una proporción. k éxitos en n ensayos."""
    if not n:
        return None, None, None
    p = k / n
    z2 = z * z
    den = 1 + z2 / n
    mid = (p + z2 / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / den
    return p, max(0.0, mid - half), min(1.0, mid + half)


def mean_ci(xs, z=Z):
    xs = [x for x in xs if x is not None]
    n = len(xs)
    if not n:
        return None, None, None
    mu = sum(xs) / n
    if n == 1:
        return mu, mu, mu
    var = sum((x - mu) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return mu, mu - z * se, mu + z * se


def shrink(obs, n, prior, n0=PRIOR_N):
    if obs is None:
        return prior
    return (n / (n + n0)) * obs + (n0 / (n + n0)) * prior


def odds_band(odds):
    if odds is None:
        return None
    try:
        o = int(odds)
    except (TypeError, ValueError):
        return None
    if o <= -200:
        return "favorito_fuerte"
    if o < 0:
        return "favorito"
    if o <= 110:
        return "par"
    if o <= 200:
        return "underdog"
    return "underdog_largo"


def ev_band(ev):
    if ev is None:
        return None
    if ev <= 0:
        return "ev_no_pos"
    if ev < 3:
        return "ev_0_3"
    if ev < 8:
        return "ev_3_8"
    return "ev_8mas"


def side_class(row):
    mk = MKT_CANON.get(row.get("market") or "", (row.get("market") or "").lower())
    sel = (row.get("selection") or "").lower()
    if mk == "total":
        return sel if sel in ("over", "under") else None
    if mk == "btts":
        return sel if sel in ("yes", "no") else None
    if mk in ("ml", "spread"):
        if sel in ("home", "away", "draw"):
            return sel
    return sel or None


def fav_dog(row):
    odds = row.get("odds")
    if odds is not None:
        try:
            return "favorito" if int(odds) < 0 else "underdog"
        except (TypeError, ValueError):
            pass
    pnv = row.get("p_nv")
    if pnv is not None:
        return "favorito" if float(pnv) >= 0.5 else "underdog"
    return None


def features(row):
    """Etiquetas reales del pick (sin inventar). Omite claves sin dato."""
    ev = ev_of(row)
    out = {
        "sport": row.get("sport") or None,
        "market": MKT_CANON.get(row.get("market") or "", None),
        "side": side_class(row),
        "fav": fav_dog(row),
        "odds_band": odds_band(row.get("odds")),
        "ev_band": ev_band(ev),
        "conf": row.get("conf_level") or None,
    }
    # señales persistidas en publish-time (json) si existen
    raw = row.get("signals_json")
    if raw:
        try:
            sigs = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            sigs = None
        if isinstance(sigs, dict):
            for k in ("steam", "rlm", "rest", "injury", "divergence_high"):
                if sigs.get(k) is not None:
                    out[k] = sigs[k]
    return {k: v for k, v in out.items() if v is not None}


def segment_keys(feat):
    """Lista de segmentos (de más ancho a más estrecho). Intersecciones sólo con las claves presentes."""
    keys = []
    sp, mk, side = feat.get("sport"), feat.get("market"), feat.get("side")
    fav, ob, evb, conf = feat.get("fav"), feat.get("odds_band"), feat.get("ev_band"), feat.get("conf")
    if sp:
        keys.append((f"Deporte: {sp}", (("sport", sp),)))
    if mk:
        keys.append((f"Mercado: {mk}", (("market", mk),)))
    if sp and mk:
        keys.append((f"{sp} · {mk}", (("sport", sp), ("market", mk))))
    if mk and side:
        keys.append((f"{mk} {side}", (("market", mk), ("side", side))))
    if sp and mk and side:
        keys.append((f"{sp} · {mk} {side}", (("sport", sp), ("market", mk), ("side", side))))
    if fav:
        keys.append((f"Lado cuota: {fav}", (("fav", fav),)))
    if sp and fav:
        keys.append((f"{sp} · {fav}", (("sport", sp), ("fav", fav))))
    if ob:
        keys.append((f"Cuota {ob}", (("odds_band", ob),)))
    if sp and mk and ob:
        keys.append((f"{sp} · {mk} · {ob}", (("sport", sp), ("market", mk), ("odds_band", ob))))
    if evb:
        keys.append((f"EV {evb}", (("ev_band", evb),)))
    if conf:
        keys.append((f"Confianza {conf}", (("conf", conf),)))
    if sp and mk and evb:
        keys.append((f"{sp} · {mk} · {evb}", (("sport", sp), ("market", mk), ("ev_band", evb))))
    for sig in ("steam", "rlm", "rest", "injury", "divergence_high"):
        if sig in feat:
            keys.append((f"Señal {sig}={feat[sig]}", ((sig, feat[sig]),)))
    # de-dup preserving order
    seen, out = set(), []
    for lab, tup in keys:
        if tup in seen:
            continue
        seen.add(tup)
        out.append((lab, tup))
    return out


def _hit(row):
    st = row.get("status")
    if st == "GANADO":
        return 1.0
    if st == "PERDIDO":
        return 0.0
    if st == "MEDIO_GANADO":
        return 0.5
    if st == "MEDIO_PERDIDO":
        return 0.5
    return None  # push no entra al % acierto


def summarize(rows, prior_roi=None, prior_hit=None):
    """Métricas + IC de un conjunto de picks calificados."""
    rows = [r for r in rows if r.get("status") in DONE]
    hits, units, clvs = [], [], []
    W = L = P = 0.0
    for r in rows:
        st = r["status"]
        if st == "GANADO":
            W += 1
        elif st == "PERDIDO":
            L += 1
        elif st == "MEDIO_GANADO":
            W += 0.5
            P += 0.5
        elif st == "MEDIO_PERDIDO":
            L += 0.5
            P += 0.5
        elif st == "PUSH":
            P += 1
        h = _hit(r)
        if h is not None:
            hits.append(h)
        u = units_of(r)
        if u is not None:
            units.append(u)
        v = clv_pct(r.get("open_odds"), r.get("odds"))
        if v is not None:
            clvs.append(v)
    n = len(rows)
    n_hit = len(hits)
    p, plo, phi = wilson(sum(hits), n_hit) if n_hit else (None, None, None)
    u_mu, u_lo, u_hi = mean_ci(units)
    c_mu, c_lo, c_hi = mean_ci(clvs)
    roi = (u_mu * 100.0) if u_mu is not None else None
    roi_lo = (u_lo * 100.0) if u_lo is not None else None
    roi_hi = (u_hi * 100.0) if u_hi is not None else None
    hit = (p * 100.0) if p is not None else None
    if prior_roi is None:
        prior_roi = 0.0
    if prior_hit is None:
        prior_hit = 50.0
    return dict(
        n=n, n_hit=n_hit, n_priced=len(units), n_clv=len(clvs),
        W=round(W, 2), L=round(L, 2), P=round(P, 2),
        hit=round(hit, 2) if hit is not None else None,
        hit_lo=round(plo * 100.0, 2) if plo is not None else None,
        hit_hi=round(phi * 100.0, 2) if phi is not None else None,
        hit_shrunk=round(shrink(hit, n_hit, prior_hit), 2) if hit is not None else None,
        units=round(sum(units), 2) if units else 0.0,
        roi=round(roi, 2) if roi is not None else None,
        roi_lo=round(roi_lo, 2) if roi_lo is not None else None,
        roi_hi=round(roi_hi, 2) if roi_hi is not None else None,
        roi_shrunk=round(shrink(roi, len(units), prior_roi), 2) if roi is not None else None,
        clv=round(c_mu, 2) if c_mu is not None else None,
        clv_lo=round(c_lo, 2) if c_lo is not None else None,
        clv_hi=round(c_hi, 2) if c_hi is not None else None,
    )


def _match(feat, tup):
    return all(feat.get(k) == v for k, v in tup)


def build_segments(rows, min_n=MIN_N):
    """Diccionario label -> {rows, stats, action} para todos los segmentos con n>=1.
    La acción (keep/stricter/block) sólo se asigna si n>=min_n."""
    rows = [r for r in rows if r.get("status") in DONE]
    global_stats = summarize(rows)
    prior_roi = global_stats.get("roi") or 0.0
    prior_hit = global_stats.get("hit") or 50.0
    buckets = defaultdict(list)
    labels = {}
    for r in rows:
        feat = features(r)
        for lab, tup in segment_keys(feat):
            buckets[tup].append(r)
            labels[tup] = lab
    out = []
    for tup, rs in buckets.items():
        st = summarize(rs, prior_roi=prior_roi, prior_hit=prior_hit)
        action, reason = "keep", None
        # sólo se bloquea un segmento que incluye deporte (evita vetar "EV 3-8" o "underdog" en todos los deportes)
        sport_specific = any(k == "sport" for k, _ in tup)
        if st["n"] >= min_n and sport_specific:
            roi_hi = st.get("roi_hi")
            hit_hi = st.get("hit_hi")
            roi_s = st.get("roi_shrunk")
            if roi_hi is not None and roi_hi < 0 and (roi_s is None or roi_s < 0):
                if hit_hi is not None and hit_hi < 50:
                    action, reason = "block", "n suficiente y acierto e ROI significativamente negativos (IC 95%)"
                else:
                    action, reason = "block", "n suficiente y ROI significativamente negativo (IC 95% por encima sigue < 0)"
            elif roi_hi is not None and roi_hi < 2 and (roi_s is not None and roi_s < 0):
                action, reason = "stricter", "ROI encogido negativo; se exige más EV y confianza Alta"
            else:
                action, reason = "keep", "se mantiene (no se relajan umbrales en segmentos positivos)"
        elif st["n"] >= min_n:
            action, reason = "keep", "segmento global (sin deporte): informativo, no bloquea"
        out.append(dict(label=labels[tup], key=list(tup), stats=st, action=action if st["n"] >= min_n else "insufficient",
                        reason=reason if st["n"] >= min_n else f"n={st['n']} < {min_n} (sin decisión, evita sobreajuste)"))
    out.sort(key=lambda x: (0 if x["action"] == "block" else 1 if x["action"] == "stricter" else 2, -(x["stats"]["n"] or 0)))
    return dict(global_stats=global_stats, segments=out, min_n=min_n, prior_n=PRIOR_N)


def decision_for(feat, segments):
    """La decisión más conservadora de los segmentos con muestra suficiente que aplican al pick."""
    worst = "keep"
    why = []
    for seg in segments or []:
        if seg.get("action") in ("insufficient", None):
            continue
        tup = tuple(tuple(x) for x in seg["key"])
        if not _match(feat, tup):
            continue
        if seg["action"] == "block":
            worst = "block"
            why.append(seg)
        elif seg["action"] == "stricter" and worst != "block":
            worst = "stricter"
            why.append(seg)
        elif seg["action"] == "keep" and not why:
            why.append(seg)
    return worst, why


def similar(row, segments, min_n=10):
    """El segmento más específico con n>=min_n que describe este pick (para 'Por qué este pick')."""
    feat = features(row)
    best = None
    for seg in segments or []:
        if (seg.get("stats") or {}).get("n", 0) < min_n:
            continue
        tup = tuple(tuple(x) for x in seg["key"])
        if not _match(feat, tup):
            continue
        # más específico = más claves
        score = (len(tup), seg["stats"]["n"])
        if best is None or score > best[0]:
            best = (score, seg)
    if not best:
        return None
    seg = best[1]
    st = seg["stats"]
    return dict(label=seg["label"], n=st["n"], hit=st["hit"], hit_lo=st["hit_lo"], hit_hi=st["hit_hi"],
                roi=st["roi"], roi_lo=st["roi_lo"], roi_hi=st["roi_hi"], clv=st["clv"],
                action=seg.get("action"), reason=seg.get("reason"),
                note="Cifras reales del récord de picks similares. No es una garantía de acierto.")


def load_graded(typ="main"):
    """Lee picks calificados de la base en vivo (sólo lectura de filas; no inventa)."""
    try:
        with history._lock:
            c = history._open()
            if c is None:
                return []
            q = "SELECT * FROM picks WHERE status IN ('GANADO','PERDIDO','PUSH','MEDIO_GANADO','MEDIO_PERDIDO')"
            args = []
            if typ:
                q += " AND type=?"
                args.append(typ)
            q += " AND start_ts>100000 ORDER BY start_ts, id"
            cur = c.execute(q, args)
            names = [d[0] for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]
    except Exception:
        return []


_cache = dict(ts=0, typ=None, data=None)


def cached_segments(typ="main", ttl=120):
    import time
    now = time.time()
    if _cache["data"] is not None and _cache["typ"] == typ and now - _cache["ts"] < ttl:
        return _cache["data"]
    data = build_segments(load_graded(typ))
    _cache.update(ts=now, typ=typ, data=data)
    return data


def workings(typ="main"):
    """Sección 'Lo que funciona / lo que no' para la API de récord."""
    data = cached_segments(typ)
    segs = data.get("segments") or []
    good, bad, strict = [], [], []
    for s in segs:
        st = s["stats"]
        item = dict(label=s["label"], n=st["n"], hit=st["hit"], hit_lo=st["hit_lo"], hit_hi=st["hit_hi"],
                    roi=st["roi"], roi_lo=st["roi_lo"], roi_hi=st["roi_hi"], clv=st["clv"],
                    action=s["action"], reason=s.get("reason"))
        if s["action"] == "block":
            bad.append(item)
        elif s["action"] == "stricter":
            strict.append(item)
        elif s["action"] == "keep" and st["n"] >= MIN_N and (st.get("roi_shrunk") or 0) > 0 and (st.get("hit") or 0) >= 52:
            good.append(item)
    # top by n
    good.sort(key=lambda x: (-(x["roi"] or -999), -x["n"]))
    bad.sort(key=lambda x: ((x["roi"] if x["roi"] is not None else 0), -x["n"]))
    return dict(
        min_n=MIN_N, prior_n=PRIOR_N,
        overall=data.get("global_stats"),
        funciona=good[:8],
        no_funciona=bad[:8],
        mas_estricto=strict[:8],
        note="Segmentos con muestra mínima y Shrinkage/IC 95%. Un segmento positivo no relaja el filtro. No es una promesa de acierto (el 80% no está respaldado por este récord).",
    )


def feedback(row, segments=None):
    """Decisión para un candidato a publicar: keep / stricter / block, con el similar."""
    segs = (segments or cached_segments("main")).get("segments") if isinstance(segments, dict) else segments
    if segs is None:
        segs = cached_segments("main").get("segments")
    feat = features(row)
    action, why = decision_for(feat, segs)
    sim = similar(row, segs)
    reason = None
    if action == "block":
        lab = why[0]["label"] if why else "segmento"
        reason = f"el récord de «{lab}» es significativamente negativo; no se publica"
    elif action == "stricter":
        lab = why[0]["label"] if why else "segmento"
        reason = f"el récord de «{lab}» es flojo; se exigen umbrales más estrictos"
    return dict(action=action, reason=reason, similar=sim, features=feat)


def snapshot_signals(analysis, cand, conf):
    """JSON persistible al publicar: señales, confianza, EV, divergencia. Sin inventar."""
    sigs = (analysis or {}).get("signals") or []
    out = dict(
        conf=(conf or {}).get("level") if isinstance(conf, dict) else conf,
        ev=cand.get("ev") if cand else None,
        edge=cand.get("edge") if cand else None,
        p_final=cand.get("p_final") if cand else None,
        divergence_high=bool(cand.get("divergence_high")) if cand else None,
        n_present=(analysis or {}).get("n_present"),
        n_agree=(analysis or {}).get("n_agree"),
        n_against=(analysis or {}).get("n_against"),
        verdicts={s["key"]: s["verdict"] for s in sigs if s.get("key")},
    )
    # flags derivados sólo si la señal tiene dato
    for s in sigs:
        figs = s.get("figures") or {}
        if s.get("key") == "movimiento" and s.get("verdict") != "sin_dato":
            tags = figs.get("tags") or []
            names = [t[0] if isinstance(t, (list, tuple)) else t for t in tags]
            out["steam"] = "STEAM" in names or "steam" in {str(x).lower() for x in names}
        if s.get("key") == "rlm" and s.get("verdict") != "sin_dato":
            out["rlm"] = s.get("verdict")
        if s.get("key") == "fisico" and s.get("verdict") != "sin_dato":
            if figs.get("rest_home") is not None or figs.get("rest_away") is not None or "back" in (s.get("detail") or "").lower() or "descanso" in (s.get("detail") or "").lower():
                out["rest"] = s.get("verdict")
        if s.get("key") == "lesiones" and s.get("verdict") != "sin_dato":
            out["injury"] = s.get("verdict")
    return {k: v for k, v in out.items() if v is not None}


def walk_forward(rows, preds_by_game, decide_fn, week_secs=7 * 86400, min_train=MIN_N):
    """Validación walk-forward por semanas de inicio. decide_fn(pick, pred, train_rows)->(keep:bool, reason)."""
    rows = sorted((r for r in rows if r.get("status") in DONE and (r.get("start_ts") or 0) > 100000),
                  key=lambda r: (r.get("start_ts") or 0, r.get("id") or 0))
    if not rows:
        return dict(folds=[], kept=[], skipped="sin picks calificados")
    t0 = rows[0]["start_ts"]
    folds, kept = [], []
    end_all = rows[-1]["start_ts"]
    fold_i = 0
    t = t0 + week_secs
    while t <= end_all + week_secs:
        train = [r for r in rows if r["start_ts"] < t]
        test = [r for r in rows if t <= r["start_ts"] < t + week_secs]
        t += week_secs
        if not test:
            continue
        if len(train) < min_train:
            # still evaluate test as "not yet enough history" → treat as old-only, new keeps none extra
            decisions = [(r, False, "train insuficiente") for r in test]
        else:
            decisions = []
            for r in test:
                pred = preds_by_game.get((r.get("league"), str(r.get("eid"))))
                ok, reason = decide_fn(r, pred, train)
                decisions.append((r, ok, reason))
        new_rows = [r for r, ok, _ in decisions if ok]
        reasons = defaultdict(int)
        for _, ok, reason in decisions:
            if not ok:
                reasons[reason or "descartado"] += 1
        fold_i += 1
        folds.append(dict(
            fold=fold_i,
            train_n=len(train),
            test_n=len(test),
            kept_n=len(new_rows),
            test=summarize(test),
            kept=summarize(new_rows),
            reasons=dict(reasons),
            window=[t - week_secs, t],
        ))
        kept.extend(new_rows)
    return dict(folds=folds, kept=kept, n_old=len(rows), n_new=len(kept))
