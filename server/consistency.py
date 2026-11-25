"""Fuente única de coherencia: predicción NRNM vs picks, análisis, confianza y récord.

No inventa datos. Las líneas de sets de tenis (sspread/stotal) no se comparan con
el hándicap/total de juegos de la predicción: no hay mercado equivalente en la carta.
Los picks ya iniciados o calificados no se reescriben.
"""
from __future__ import annotations
import json
import time
from statistics import median

from .odds import am_to_dec

LINE_TOL = 1e-6
SET_MARKETS = frozenset({"sspread", "stotal"})
MK_CANON = {
    "ml": "ML", "ML": "ML",
    "spread": "Spread", "Spread": "Spread",
    "total": "Total", "Total": "Total", "ou": "OU", "OU": "Total",
    "btts": "BTTS", "BTTS": "BTTS",
    "sspread": "sspread", "stotal": "stotal",
}

# CDMX fijo UTC-6 (México sin horario de verano en esta app)
CDMX_OFF = -6 * 3600


def canon_market(mk):
    if not mk:
        return None
    return MK_CANON.get(mk, mk)


def line_close(a, b, tol=LINE_TOL):
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def ev_as_pct(ev):
    if ev is None:
        return None
    ev = float(ev)
    return ev * 100.0 if abs(ev) <= 1.0 else ev


def clamp_display_confidence(conf, status=None, ev=None):
    """No mostrar confianza Alta (ni Media como si fuera pick fuerte) en PASS o EV≤0."""
    out = dict(conf or {})
    evp = ev_as_pct(ev) if ev is not None else None
    st = (status or "").upper()
    blocked = st in ("PASS", "SIN_LINEA", "REVISAR") or (evp is not None and evp <= 0)
    if blocked:
        if out.get("level") == "Alta" or st in ("PASS", "SIN_LINEA") or (evp is not None and evp <= 0):
            out["level"] = "no aplica"
            out["capped_display"] = True
            out["cap_reason"] = "PASS, REVISAR o EV≤0: no se muestra confianza Alta"
    return out


def _relabel(label, old_line, new_line):
    if not label or old_line is None or new_line is None:
        return label
    def fmt(x):
        x = float(x)
        return str(int(x)) if x == int(x) else f"{x:g}"
    s = str(label)
    candidates = []
    try:
        ol = float(old_line)
        for t in (f"{ol:g}", f"{ol:.1f}", f"{ol:+g}", f"{ol:+.1f}", str(old_line)):
            if t and t in s and t not in candidates:
                candidates.append(t)
    except (TypeError, ValueError):
        return label
    if not candidates:
        return label
    return s.replace(candidates[0], fmt(new_line), 1)


def pred_target(pred, market, selection=None):
    """Lado/línea de la predicción para un mercado de pick. None = no comparable (omitir)."""
    if not pred:
        return None
    mk = canon_market(market)
    if mk in SET_MARKETS:
        return None
    if mk == "ML":
        w = pred.get("winner") or {}
        if w.get("side") is None:
            return None
        return dict(side=w["side"], line=None, label=None, home_line=None)
    if mk in ("Total", "OU"):
        t = pred.get("total") or {}
        if t.get("side") is None:
            return None
        return dict(side=t.get("side"), line=t.get("line"), label=t.get("label"), home_line=None)
    if mk == "Spread":
        s = pred.get("spread") or {}
        if s.get("side") is None:
            return None
        home_line = s.get("line")
        pick_line = None
        if home_line is not None and selection:
            try:
                pick_line = float(home_line) if selection == "home" else -float(home_line)
            except (TypeError, ValueError):
                pick_line = None
        elif home_line is not None:
            try:
                pick_line = float(home_line)
            except (TypeError, ValueError):
                pick_line = None
        return dict(side=s.get("side"), line=pick_line, label=s.get("label"), home_line=home_line)
    if mk == "BTTS":
        b = pred.get("btts") or {}
        if b.get("side") is None:
            return None
        return dict(side=b.get("side"), line=None, label=b.get("label"), home_line=None)
    return None


def classify_pick(pred, row):
    """'ok' | 'mismatch' | 'skip'. row: market/selection/line (DB o candidato)."""
    if not row:
        return "skip", "sin pick"
    mk = row.get("market") or row.get("mkt")
    sel = row.get("selection") or row.get("side")
    line = row.get("line")
    if canon_market(mk) in SET_MARKETS:
        return "skip", "mercado de sets (no está en la carta de predicción de juegos)"
    tgt = pred_target(pred, mk, sel)
    if tgt is None:
        return "skip", "sin mercado equivalente en la predicción"
    if not sel:
        return "skip", "sin lado"
    if sel != tgt["side"]:
        return "mismatch", "lado"
    mk_c = canon_market(mk)
    if mk_c in ("Total", "OU", "Spread") and tgt.get("line") is not None and line is not None:
        # para spread, comparar en línea del local
        if mk_c == "Spread":
            try:
                cand_home = float(line) if sel == "home" else -float(line)
            except (TypeError, ValueError):
                return "mismatch", "línea"
            if tgt.get("home_line") is not None and not line_close(cand_home, tgt["home_line"]):
                return "mismatch", "línea"
        elif not line_close(line, tgt["line"]):
            return "mismatch", "línea"
    return "ok", None


def pick_as_cand(row):
    return dict(
        market=canon_market(row.get("market")),
        side=row.get("selection") or row.get("side"),
        line=row.get("line"),
        label=row.get("label"),
        status=row.get("status") or "PICK",
    )


def updated_label(row, tgt):
    if tgt.get("label"):
        # no reusar etiqueta de otro lado
        return tgt["label"]
    return _relabel(row.get("label"), row.get("line"), tgt.get("line")) or row.get("label")


def cdmx_date(ts=None):
    return time.strftime("%Y-%m-%d", time.gmtime((ts if ts is not None else time.time()) + CDMX_OFF))


def day_window(date=None, now=None):
    """Inicio y fin UNIX (exclusivo el fin) de un día CDMX. date='YYYY-MM-DD' o hoy."""
    date = date or cdmx_date(now)
    # medianoche CDMX = 06:00 UTC
    parts = [int(x) for x in date.split("-")]
    import calendar
    start = calendar.timegm((parts[0], parts[1], parts[2], 0, 0, 0)) - CDMX_OFF
    return int(start), int(start + 86400), date


def _rows(sql, args=()):
    from . import history, prediction as PRED
    with history._lock:
        c = history._open()
        if c is None:
            return []
        try:
            PRED._c()
        except Exception:
            pass
        cur = c.execute(sql, args)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def _load_pred(league, eid, cache=None):
    if cache is not None and (league, str(eid)) in cache:
        return cache[(league, str(eid))]
    rows = _rows("SELECT payload FROM predictions WHERE league=? AND eid=?", (league, str(eid)))
    pred = None
    if rows:
        pred = json.loads(rows[0]["payload"] or "null")
    if cache is not None:
        cache[(league, str(eid))] = pred
    return pred


def pending_mismatches(now=None, since_ts=None, only_open=True, date=None):
    """Picks PENDIENTE que no coinciden con la predicción guardada (lado o línea)."""
    now = int(now or time.time())
    if date:
        lo, hi, _ = day_window(date, now)
        if since_ts is None:
            since_ts = lo
        until = hi
    else:
        until = None
        if since_ts is None:
            # hoy CDMX en adelante (incluye próximos)
            since_ts, _, _ = day_window(cdmx_date(now), now)
    q = "SELECT * FROM picks WHERE status='PENDIENTE' AND start_ts>=?"
    args = [int(since_ts)]
    if until is not None:
        q += " AND start_ts<?"
        args.append(int(until))
    if only_open:
        q += " AND start_ts>?"
        args.append(now)
    q += " ORDER BY start_ts, league, eid, (type='main') DESC, id"
    cache = {}
    out = []
    for r in _rows(q, tuple(args)):
        pred = _load_pred(r["league"], r["eid"], cache)
        if pred is None:
            # sin predicción no se puede afirmar contradicción
            continue
        kind, reason = classify_pick(pred, r)
        if kind != "mismatch":
            continue
        locked = int(r["start_ts"] or 0) <= now
        out.append(dict(
            type="pred_vs_registered",
            reason=reason,
            locked=locked,
            open=not locked,
            sport=r.get("sport"), league=r.get("league"), eid=str(r.get("eid")),
            home=r.get("home"), away=r.get("away"),
            market=r.get("market"), selection=r.get("selection"), line=r.get("line"),
            label=r.get("label"), pick_type=r.get("type"), state=r.get("state"),
            start_ts=r.get("start_ts"), id=r.get("id"),
        ))
    return out


def lean_mismatch(pred, lean, status=None):
    """Contradicción del lean de Mejores picks vs la predicción (ignora sets)."""
    if not lean:
        return None
    row = dict(market=lean.get("market"), selection=lean.get("side"), line=lean.get("line"), label=lean.get("label"))
    kind, reason = classify_pick(pred, row)
    if kind == "mismatch":
        return dict(type="pred_vs_mejores_picks", reason=reason, label=lean.get("label"),
                    market=lean.get("market"), side=lean.get("side"), line=lean.get("line"),
                    status=status)
    return None


def analysis_winner_conflict(detail, pred):
    """True si el texto del análisis atribuye al ganador un pFinal distinto al de la predicción."""
    if not detail or not pred:
        return False
    w = (pred.get("winner") or {})
    # el texto viejo «pFinal 49.0% … ganador pFinal: away (60.8%)» confunde; el nuevo etiqueta pFinal del pick
    text = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
    if "pFinal del pick" in text or "ganador (mismo pFinal" in text:
        return False
    # patrón legacy: un pFinal porcentual seguido de un ganador pFinal con otro porcentaje
    import re
    m = re.search(r"pFinal\s+(\d+(?:\.\d+)?)%.+ganador pFinal:\s*(\w+)\s*\((\d+(?:\.\d+)?)%\)", text)
    if not m:
        return False
    pick_p, side, win_p = float(m.group(1)), m.group(2), float(m.group(3))
    if abs(pick_p - win_p) > 0.15:  # claramente dos números distintos
        wside = w.get("side")
        if wside and side != wside:
            return True
        # mismo lado o no: igual es wording confuso si 49 vs 60.8
        return True
    return False


def chat_consistency(a):
    """Bloque explícito para el LLM: un solo ganador pFinal y las contradicciones, si las hay."""
    p = (a or {}).get("pred") or {}
    w = p.get("winner") or {}
    pk = (a or {}).get("picks") or {}
    lean = pk.get("lean") or {}
    conf = clamp_display_confidence(pk.get("confidence"), pk.get("status"), lean.get("ev") if lean else None)
    flags = []
    lm = lean_mismatch(p, lean, pk.get("status")) if lean else None
    if lm:
        flags.append(f"lean {lean.get('label')} no coincide con la predicción ({lm['reason']})")
    rec_bad = []
    for r in (a or {}).get("record") or []:
        if (r.get("status") or "") == "ANULADO":
            continue
        kind, reason = classify_pick(p, r)
        if kind == "mismatch":
            rec_bad.append(f"{r.get('label')} ({reason})")
    an = pk.get("analysis") or (a or {}).get("analysis") or {}
    modelo = next((s for s in (an.get("signals") or []) if s.get("key") == "modelo"), None)
    if modelo and analysis_winner_conflict(modelo.get("detail") or "", p):
        flags.append("el análisis mezcla el pFinal del pick con el ganador pFinal")
    evp = ev_as_pct(lean.get("ev")) if lean and lean.get("ev") is not None else None
    if (pk.get("status") or "").upper() in ("PASS", "SIN_LINEA") or (evp is not None and evp <= 0):
        if (pk.get("confidence") or {}).get("level") == "Alta" and not conf.get("capped_display"):
            flags.append("confianza Alta en PASS o EV≤0")
    return dict(
        ganador_pfinal=dict(side=w.get("side"), p=w.get("p"), src=w.get("src") or "pfinal"),
        pfinal_del_pick=lean.get("p_final"),
        nota="El pFinal del pick (hándicap o total) no es el ganador del juego. El ganador es ganador_pfinal.",
        confianza_mostrada=conf.get("level"),
        pick_publicado=bool(pk.get("published")),
        estado_mejores=pk.get("status"),
        contradicciones=flags + [f"registrado: {x}" for x in rec_bad],
        regla=("Nunca recomiendes un lado o una línea distinto al de la Predicción NRNM. "
               "Si hay contradicciones, dilo y quédate con la predicción. "
               "PASS o EV≤0 no es recomendación y la confianza no es Alta."),
    )


def audit_from_analysis(a, now=None):
    """Contradicciones visibles en un análisis (pred vs registro / mejores / análisis / confianza)."""
    now = int(now or time.time())
    items = []
    if not a:
        return items
    g = a.get("game") or {}
    p = a.get("pred") or {}
    pk = a.get("picks") or {}
    lean = pk.get("lean") or {}
    base = dict(sport=g.get("sport"), league=g.get("league"), eid=str(g.get("id") or ""),
                home=(g.get("home") or {}).get("name"), away=(g.get("away") or {}).get("name"),
                start_ts=None, locked=g.get("state") != "pre")
    for r in a.get("record") or []:
        if (r.get("status") or "") == "ANULADO":
            continue
        kind, reason = classify_pick(p, r)
        if kind == "mismatch":
            items.append(dict(base, type="pred_vs_registered", reason=reason, label=r.get("label"),
                              market=r.get("market"), selection=r.get("selection"), line=r.get("line"),
                              pick_type=r.get("type"), open=g.get("state") == "pre"))
    lm = lean_mismatch(p, lean, pk.get("status"))
    if lm:
        items.append(dict(base, **lm, open=g.get("state") == "pre"))
    an = pk.get("analysis") or a.get("analysis") or {}
    modelo = next((s for s in (an.get("signals") or []) if s.get("key") == "modelo"), None)
    if modelo and analysis_winner_conflict(modelo.get("detail") or "", p):
        items.append(dict(base, type="pred_vs_analisis", reason="pFinal del pick presentado como ganador",
                          detail=modelo.get("detail"), open=g.get("state") == "pre"))
    evp = ev_as_pct(lean.get("ev")) if lean and lean.get("ev") is not None else None
    st = (pk.get("status") or "").upper()
    level = (pk.get("confidence") or {}).get("level")
    if level == "Alta" and (st in ("PASS", "SIN_LINEA", "REVISAR") or (evp is not None and evp <= 0)):
        items.append(dict(base, type="confidence_vs_pass_ev", reason="confianza Alta en PASS/EV≤0",
                          level=level, status=st, ev=evp, open=g.get("state") == "pre"))
    return items


def count_by_type(items):
    out = {}
    for it in items or []:
        k = it.get("type") or "other"
        out[k] = out.get(k, 0) + 1
    return out


# ---------- desempeño real: predicciones vs picks principales ----------
def _profit(status, odds):
    from . import record as REC
    return REC.profit(status, odds)


def _close_price(c, league, eid, start_ts, market, side, line):
    """Última cuota pre-saque en `lines` para ese mercado/lado/línea. Prefiere book pin; si no, mediana."""
    args = [league, str(eid), market, side, int(start_ts)]
    if line is None:
        sql = "SELECT book, price, ts FROM lines WHERE league=? AND eid=? AND market=? AND side=? AND ts<=? AND price IS NOT NULL"
    else:
        sql = "SELECT book, price, ts FROM lines WHERE league=? AND eid=? AND market=? AND side=? AND ts<=? AND price IS NOT NULL AND line IS NOT NULL AND ABS(line-?)<1e-6"
        args.append(float(line))
    rows = list(c.execute(sql, args))
    if not rows:
        return None, None
    last_ts = max(r[2] for r in rows)
    at = [r for r in rows if r[2] == last_ts]
    pin = next((r for r in at if (r[0] or "") in ("pin", "pinnacle", "Pinnacle")), None)
    if pin and pin[1] is not None:
        return int(pin[1]), pin[0]
    prices = [int(r[1]) for r in at if r[1] is not None]
    if not prices:
        return None, None
    # mediana; si hay empate, el más cercano a -110
    try:
        mid = median(prices)
        best = min(prices, key=lambda x: (abs(x - mid), abs(x + 110)))
        book = next((r[0] for r in at if int(r[1]) == best), at[0][0])
        return int(best), book
    except Exception:
        return int(prices[0]), at[0][0]


def _agg_rows(rows):
    """rows: dicts con status y opcionalmente units/odds. Pushes fuera del hit%; ROI a 1u con cuota disponible."""
    W = L = P = 0.0
    units = 0.0
    n_priced = 0
    n_unpriced = 0
    for r in rows:
        s = r.get("status")
        if s in ("GANADO",):
            W += 1
        elif s in ("PERDIDO",):
            L += 1
        elif s == "PUSH":
            P += 1
        elif s == "MEDIO_GANADO":
            W += 0.5
            P += 0.5
        elif s == "MEDIO_PERDIDO":
            L += 0.5
            P += 0.5
        else:
            continue
        u = r.get("units") if r.get("odds") is not None else None
        if u is None and r.get("odds") is not None:
            u = _profit(s, r.get("odds"))
        if u is None:
            n_unpriced += 1
        else:
            units += u
            n_priced += 1
    n = W + L
    return dict(
        n=int(round(W + L + P)) if P else int(W + L) if (W + L) == int(W + L) else W + L,
        n_dec=W + L + P,
        hit=W, miss=L, push=P,
        n_hit=W + L,
        hit_pct=(W / (W + L) * 100 if (W + L) else None),
        n_priced=n_priced, n_unpriced=n_unpriced,
        units=round(units, 2) if n_priced else None,
        roi=(units / n_priced * 100 if n_priced else None),
    )


def _group_add(dst, key, row):
    dst.setdefault(key, []).append(row)


def compare_pred_vs_picks():
    """Hit% y ROI reales: predicciones mostradas (ML/total/hándicap) vs picks principales registrados.

    ROI de predicciones sólo cuando hay cuota pre-saque en la tabla `lines` (no se inventa).
    ROI de picks usa `units` guardadas o, si faltan, la cuota registrada.
    """
    from . import history
    pred_rows = []
    pick_rows = []
    with history._lock:
        c = history._open()
        if c is None:
            return dict(predictions={}, mains={}, note="sin base de datos")
        preds = list(c.execute(
            "SELECT league,eid,sport,start_ts,home,away,payload,r_ml,r_total,r_spread,status FROM predictions WHERE status='GRADED'"
        ))
        for r in preds:
            keys = ["league", "eid", "sport", "start_ts", "home", "away", "payload", "r_ml", "r_total", "r_spread", "status"]
            row = dict(zip(keys, r))
            p = json.loads(row.pop("payload") or "null") or {}
            sport = row["sport"]
            # ML / ganador
            if row.get("r_ml") in ("GANADO", "PERDIDO", "PUSH", "MEDIO_GANADO", "MEDIO_PERDIDO"):
                w = (p.get("winner") or {})
                price, book = _close_price(c, row["league"], row["eid"], row["start_ts"], "ml", w.get("side"), None)
                pred_rows.append(dict(source="pred", market="ml", sport=sport, status=row["r_ml"],
                                      odds=price, book=book, side=w.get("side")))
            if row.get("r_total") in ("GANADO", "PERDIDO", "PUSH", "MEDIO_GANADO", "MEDIO_PERDIDO"):
                t = p.get("total") or {}
                price, book = _close_price(c, row["league"], row["eid"], row["start_ts"], "total", t.get("side"), t.get("line"))
                pred_rows.append(dict(source="pred", market="total", sport=sport, status=row["r_total"],
                                      odds=price, book=book, side=t.get("side"), line=t.get("line")))
            if row.get("r_spread") in ("GANADO", "PERDIDO", "PUSH", "MEDIO_GANADO", "MEDIO_PERDIDO"):
                s = p.get("spread") or {}
                home_line = s.get("line")
                side = s.get("side")
                line = None
                if home_line is not None and side:
                    try:
                        line = float(home_line) if side == "home" else -float(home_line)
                    except (TypeError, ValueError):
                        line = None
                price, book = _close_price(c, row["league"], row["eid"], row["start_ts"], "spread", side, line)
                pred_rows.append(dict(source="pred", market="spread", sport=sport, status=row["r_spread"],
                                      odds=price, book=book, side=side, line=line))
        for r in c.execute(
            "SELECT sport, market, status, units, odds FROM picks "
            "WHERE type='main' AND status IN ('GANADO','PERDIDO','PUSH','MEDIO_GANADO','MEDIO_PERDIDO')"
        ):
            pick_rows.append(dict(source="main", sport=r[0], market=r[1], status=r[2], units=r[3], odds=r[4]))

    def pack(rows):
        by_m, by_s, by_sm = {}, {}, {}
        for r in rows:
            _group_add(by_m, r.get("market") or "?", r)
            _group_add(by_s, r.get("sport") or "?", r)
            _group_add(by_sm, f"{r.get('sport') or '?'}|{r.get('market') or '?'}", r)
        return dict(
            overall=_agg_rows(rows),
            by_market={k: _agg_rows(v) for k, v in sorted(by_m.items())},
            by_sport={k: _agg_rows(v) for k, v in sorted(by_s.items())},
            by_sport_market={k: _agg_rows(v) for k, v in sorted(by_sm.items())},
        )

    return dict(
        predictions=pack(pred_rows),
        mains=pack(pick_rows),
        notes=(
            "Hit% = aciertos / (aciertos + fallos), sin devoluciones (PUSH). "
            "ROI de predicciones a 1u con la última cuota pre-saque de la tabla lines "
            "(Pinnacle si está en ese instante; si no, mediana de casas). "
            "Si no hay cuota para esa línea, el juego cuenta en el hit% pero no en el ROI. "
            "ROI de picks principales: units registradas (cuota del pick). "
            "Las predicciones cubren casi todos los juegos; los picks principales son un subconjunto filtrado. No son la misma muestra."
        ),
    )


# ---------- picks que concuerdan: predicción + registro (mismo mercado/lado/línea) ----------
AGREE_NOTE = (
    "Que el pick registrado y la Predicción NRNM coincidan no garantiza acierto. "
    "Es una estimación del modelo, no una garantía de ganancia."
)

_CONF_RANK = {"Alta": 3, "Media": 2, "Baja": 1, "no aplica": 0}


def _odds_txt(odds):
    from .odds import fmt_am
    if odds is None:
        return None
    try:
        return fmt_am(int(odds))
    except (TypeError, ValueError):
        return None


def _game_title(home, away, sport):
    home, away = home or "local", away or "visitante"
    if sport in ("futbol", "tenis"):
        return f"{home} vs {away}"
    return f"{away} @ {home}"


def _kickoff_cdmx(ts):
    if ts is None:
        return None
    t = time.gmtime(int(ts) + CDMX_OFF)
    months = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    h, ampm = t.tm_hour % 12 or 12, ("a.m." if t.tm_hour < 12 else "p.m.")
    return f"{t.tm_mday} {months[t.tm_mon-1]}, {h}:{t.tm_min:02d} {ampm} CDMX"


def _signals_brief(row):
    raw = row.get("signals_json")
    if not raw:
        why = row.get("why_json")
        if why:
            try:
                w = json.loads(why) if isinstance(why, str) else why
                raw = w.get("signals") if isinstance(w, dict) else None
            except Exception:
                raw = None
    if not raw:
        return None
    try:
        sig = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None
    if not isinstance(sig, dict):
        return None
    n_ag, n_pr = sig.get("n_agree"), sig.get("n_present")
    verdicts = sig.get("verdicts") or {}
    bits = []
    if n_ag is not None and n_pr is not None:
        bits.append(f"{n_ag} a favor / {n_pr} con dato")
    labels = dict(modelo="modelo", movimiento="movimiento", rlm="RLM", tendencias="tendencias",
                  lesiones="lesiones", fisico="físico")
    verd_es = dict(a_favor="a favor", en_contra="en contra", mixto="mixto", neutral="neutral", sin_dato="sin dato")
    det = []
    for k, lab in labels.items():
        v = verdicts.get(k)
        if v:
            det.append(f"{lab}: {verd_es.get(v, v)}")
    if det:
        bits.append("; ".join(det))
    return " · ".join(bits) if bits else None


def _similar_brief(row):
    try:
        from . import learn
        mk = {"ml": "ML", "spread": "Spread", "total": "Total", "btts": "BTTS",
              "sspread": "Spread", "stotal": "Total"}.get(row.get("market"), row.get("market"))
        fb = learn.feedback(dict(
            sport=row.get("sport"), market=mk, selection=row.get("selection"),
            line=row.get("line"), odds=row.get("odds"), ev=row.get("ev"),
            conf_level=row.get("conf_level"), p_final=row.get("p_final"),
            p_nv=row.get("p_nv"), edge=row.get("edge"),
        ))
        sim = (fb or {}).get("similar")
        if not sim:
            return None
        return dict(
            label=sim.get("label"), n=sim.get("n"),
            hit_pct=sim.get("hit"), hit_lo=sim.get("hit_lo"), hit_hi=sim.get("hit_hi"),
            roi=sim.get("roi"),
            note=sim.get("note") or "Cifras reales del récord de picks similares. No es una garantía de acierto.",
        )
    except Exception:
        return None


def agreeing_picks(now=None, date=None, include_live=True):
    """Picks registrados (principal + sugerencias) de hoy que coinciden en mercado, lado y línea con la predicción.

    Por defecto incluye juegos aún no empezados y, si include_live, los que ya empezaron hoy y siguen PENDIENTE
    (pick bloqueado al inicio). No incluye calificados ni anulados. No inventa filas.
    Los mercados de sets de tenis se omiten si la predicción no los cubre.
    """
    now = int(now or time.time())
    lo, hi, day = day_window(date, now)
    # asegurar tabla predictions
    try:
        _load_pred("_", "_")
    except Exception:
        pass
    q = ("SELECT * FROM picks WHERE status='PENDIENTE' AND start_ts>=? AND start_ts<?")
    args = [int(lo), int(hi)]
    if not include_live:
        q += " AND start_ts>?"
        args.append(now)
    q += " ORDER BY start_ts, league, eid, (type='main') DESC, id"
    cache = {}
    items = []
    for r in _rows(q, tuple(args)):
        pred = _load_pred(r["league"], r["eid"], cache)
        if not pred:
            continue
        kind, _reason = classify_pick(pred, r)
        if kind != "ok":
            continue
        evp = ev_as_pct(r.get("ev")) if r.get("ev") is not None else None
        conf = clamp_display_confidence(
            dict(level=r.get("conf_level")) if r.get("conf_level") else {},
            status=None,
            ev=r.get("ev"),
        )
        started = int(r.get("start_ts") or 0) <= now
        sport = r.get("sport")
        home, away = r.get("home"), r.get("away")
        items.append(dict(
            sport=sport, league=r.get("league"), eid=str(r.get("eid")),
            home=home, away=away,
            game=_game_title(home, away, sport),
            kickoff_ts=r.get("start_ts"),
            kickoff_cdmx=_kickoff_cdmx(r.get("start_ts")),
            kickoff_iso=time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(int(r["start_ts"]))) if r.get("start_ts") else None,
            live=started,
            type=r.get("type") or "suggestion",
            market=r.get("market"), selection=r.get("selection"), line=r.get("line"),
            pick=r.get("label"),
            odds=r.get("odds"), book=r.get("book"),
            odds_txt=_odds_txt(r.get("odds")),
            p_final=r.get("p_final"), ev=evp,
            confidence=(conf.get("level") if conf.get("level") else (r.get("conf_level") or "sin dato")),
            signals=_signals_brief(r),
            similar=_similar_brief(r),
            href=f"#/juego/{r.get('league')}/{r.get('eid')}",
        ))
    try:
        from . import policy as POL
        H = POL.history(_rows)
        for it in items:
            pc = POL.check(dict(p_final=it.get("p_final"), ev_pct=it.get("ev"), sport=it.get("sport"), market=it.get("market"), live=it.get("live")), H, now=now)
            it["approved"], it["locks"], it["tier"] = pc["approved"], pc["locks"], pc["tier"]
    except Exception:
        pass
    def _key(it):
        ev = it.get("ev")
        return (
            not it.get("approved", True),
            ev is None,
            -(ev if ev is not None else 0),
            -_CONF_RANK.get(it.get("confidence") or "", 0),
            0 if it.get("type") == "main" else 1,
            it.get("kickoff_ts") or 0,
        )
    items.sort(key=_key)
    return dict(
        date=day, now=now, include_live=bool(include_live),
        n=len(items), items=items, note=AGREE_NOTE,
    )



def format_agreeing_text(report):
    """Texto plano para el chat (servidor). Sin inventar ítems."""
    items = (report or {}).get("items") or []
    day = (report or {}).get("date") or ""
    live_on = (report or {}).get("include_live")
    if not items:
        ambito = "en los juegos de hoy que aún no empiezan" + (" ni en los que están en vivo" if live_on else "")
        return (
            f"Hoy ({day}) no hay picks registrados que coincidan con la Predicción NRNM {ambito}. "
            "No invento ninguno. Puede que aún no se haya registrado un pick, o que el registrado no coincida en lado o línea.\n\n"
            + AGREE_NOTE
        )
    extra = ""
    if live_on and any(it.get("live") for it in items):
        extra = ", incluyendo juegos en vivo (pick bloqueado al inicio)"
    lines = [
        f"Picks de hoy ({day}) que concuerdan: el pick registrado y la Predicción NRNM coinciden en mercado, lado y línea. "
        f"{len(items)} en total{extra}:"
    ]
    for i, it in enumerate(items, 1):
        typ = "Principal" if it.get("type") == "main" else "Sugerencia"
        cuota = it.get("odds_txt") or "sin cuota"
        if it.get("book"):
            cuota = f"{cuota} · {it['book']}"
        when = it.get("kickoff_cdmx") or "hora sin dato"
        live = " · EN VIVO (bloqueado al inicio)" if it.get("live") else ""
        ev = it.get("ev")
        evs = "sin dato" if ev is None else f"{ev:+.1f}%"
        pf = it.get("p_final")
        pfs = "sin dato" if pf is None else (f"{pf*100:.1f}%" if abs(float(pf)) <= 1.5 else f"{float(pf):.1f}%")
        pick = it.get("pick") or "—"
        game = it.get("game") or ""
        sport = (it.get("sport") or "").upper()
        conf = it.get("confidence") or "sin dato"
        lines.append(f"{i}. [{typ}] {pick} ({cuota}) — {game} · {sport} · {when}{live}")
        lines.append(f"   pFinal {pfs} · EV {evs} · confianza {conf}")
        if it.get("locks"):
            lines.append("   🔒 No se recomienda: " + "; ".join(l["reason"] for l in it["locks"]))
        if it.get("signals"):
            lines.append(f"   Señales: {it['signals']}")
        else:
            lines.append("   Señales: sin dato")
        sim = it.get("similar")
        if sim and sim.get("n"):
            hit = sim.get("hit_pct")
            hit_s = f"{hit:.0f}%" if isinstance(hit, (int, float)) else "sin %"
            lab = sim.get("label") or "segmento"
            lines.append(f"   Picks parecidos ({lab}): {hit_s} de acierto en n={sim['n']} (récord real, no es una garantía).")
        else:
            lines.append("   Picks parecidos: aún no hay muestra suficiente en el récord.")
    lines.append("")
    lines.append(AGREE_NOTE)
    return "\n".join(lines)


def format_agreeing_html(report):
    """HTML para /api/chat y tests. El frontend tambien formatea en JS."""
    import html as _html
    esc = _html.escape
    items = (report or {}).get("items") or []
    text_fallback = format_agreeing_text(report)
    if not items:
        return "<p>" + esc(text_fallback).replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"
    head = text_fallback.split(":")[0] + ":"
    parts = [esc(head), "<ol class=\"ch-agree\">"]
    for it in items:
        typ = "Principal" if it.get("type") == "main" else "Sugerencia"
        cuota = esc(it.get("odds_txt") or "sin cuota")
        if it.get("book"):
            cuota += " · " + esc(it["book"])
        href = esc(it.get("href") or "#/")
        live = " · <b>EN VIVO</b> (bloqueado al inicio)" if it.get("live") else ""
        ev = it.get("ev")
        evs = "sin dato" if ev is None else f"{ev:+.1f}%"
        pf = it.get("p_final")
        pfs = "sin dato" if pf is None else (f"{float(pf)*100:.1f}%" if abs(float(pf)) <= 1.5 else f"{float(pf):.1f}%")
        sim = it.get("similar") or {}
        if sim.get("n"):
            hit = sim.get("hit_pct")
            hit_s = f"{hit:.0f}%" if isinstance(hit, (int, float)) else "sin %"
            sim_s = (
                f"Picks parecidos ({esc(sim.get('label') or 'segmento')}): <b>{hit_s}</b> "
                f"de acierto en <b>n={int(sim['n'])}</b> (récord real, no es una garantía)."
            )
        else:
            sim_s = "Picks parecidos: aún no hay muestra suficiente en el récord."
        sig = esc(it.get("signals") or "sin dato")
        pick = esc(it.get("pick") or "—")
        game = esc(it.get("game") or "")
        sport = esc((it.get("sport") or "").upper())
        when = esc(it.get("kickoff_cdmx") or "")
        conf = esc(it.get("confidence") or "sin dato")
        parts.append(
            f"<li><b>[{typ}] {pick}</b> ({cuota}) — "
            f"<a href=\"{href}\">{game}</a> · {sport} · {when}{live}<br>"
            f"pFinal {esc(pfs)} · EV {esc(evs)} · confianza {conf}<br>"
            f"Señales: {sig}<br>{sim_s}"
            + ("<br>🔒 No se recomienda: " + esc("; ".join(l["reason"] for l in it["locks"])) if it.get("locks") else "") + "</li>"
        )
    parts.append("</ol>")
    parts.append(f"<p class=\"ch-mut\">{esc(AGREE_NOTE)}</p>")
    return "".join(parts)
