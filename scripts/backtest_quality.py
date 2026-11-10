#!/usr/bin/env python3
"""Backtest en papel del filtro de calidad contra picks YA calificados en history.db.

No se reescribe la base. Números honestos: si un dato (lesiones, clima, forma)
no está guardado en el histórico, la señal queda «sin dato».
Comparación: conjunto actual (picks type=main calificados) vs el mismo conjunto
pasado por el filtro nuevo (y variantes de umbral en un split de entrenamiento).

Uso: python scripts/backtest_quality.py [ruta/history.db]
"""
from __future__ import annotations
import json, os, sqlite3, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.record import clv_pct
from server.core import decimal
from server import quality as Q

DONE = ("GANADO", "PERDIDO", "PUSH", "MEDIO_GANADO", "MEDIO_PERDIDO")
WIN = ("GANADO", "MEDIO_GANADO")
LOSS = ("PERDIDO", "MEDIO_PERDIDO")


def _units(row):
    if row.get("units") is not None:
        try:
            return float(row["units"])
        except (TypeError, ValueError):
            pass
    st, odds = row.get("status"), row.get("odds")
    if st not in DONE or odds is None or st == "PUSH":
        return 0.0 if st == "PUSH" else None
    try:
        profit = decimal(odds) - 1.0
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


def _metrics(rows):
    W = L = P = 0.0
    units = 0.0
    n_priced = 0
    clvs = []
    by = defaultdict(lambda: dict(W=0.0, L=0.0, units=0.0, n=0, n_priced=0, clvs=[]))
    for r in rows:
        st = r["status"]
        if st == "GANADO":
            W += 1
        elif st == "PERDIDO":
            L += 1
        elif st == "MEDIO_GANADO":
            W += 0.5; P += 0.5
        elif st == "MEDIO_PERDIDO":
            L += 0.5; P += 0.5
        elif st == "PUSH":
            P += 1
        u = _units(r)
        if u is not None and st in DONE:
            units += u
            n_priced += 1
        v = clv_pct(r.get("open_odds"), r.get("odds"))
        if v is not None:
            clvs.append(v)
        sp = r.get("sport") or "?"
        b = by[sp]
        b["n"] += 1
        if st == "GANADO":
            b["W"] += 1
        elif st == "PERDIDO":
            b["L"] += 1
        elif st == "MEDIO_GANADO":
            b["W"] += 0.5
        elif st == "MEDIO_PERDIDO":
            b["L"] += 0.5
        if u is not None and st in DONE:
            b["units"] += u
            b["n_priced"] += 1
        if v is not None:
            b["clvs"].append(v)
    def pack(W, L, units, n, n_priced, clvs, extra=None):
        d = dict(n=n, graded=n, W=round(W, 2), L=round(L, 2),
                 hit_rate=(round(W / (W + L) * 100, 2) if (W + L) else None),
                 units=round(units, 2), n_priced=n_priced,
                 roi=(round(units / n_priced * 100, 2) if n_priced else None),
                 clv=(round(sum(clvs) / len(clvs), 2) if clvs else None), clv_n=len(clvs))
        if extra:
            d.update(extra)
        return d
    sports = {k: pack(v["W"], v["L"], v["units"], v["n"], v["n_priced"], v["clvs"]) for k, v in sorted(by.items())}
    return pack(W, L, units, len(rows), n_priced, clvs, extra=dict(by_sport=sports))


def _load(path):
    uri = f"file:{path}?mode=ro"
    c = sqlite3.connect(uri, uri=True)
    c.row_factory = sqlite3.Row
    cols = {r[1] for r in c.execute("PRAGMA table_info(picks)")}
    want = "id,sport,league,eid,start_ts,market,selection,line,odds,open_odds,units,status,type,p_model,p_final,p_nv,edge,ev,conf_level,created_at"
    have = [x.strip() for x in want.split(",") if x.strip() in cols]
    rows = [dict(r) for r in c.execute(
        f"SELECT {','.join(have)} FROM picks WHERE status IN ({','.join('?'*len(DONE))}) AND IFNULL(type,'main')='main'",
        DONE)]
    preds = {}
    try:
        for r in c.execute("SELECT league,eid,payload FROM predictions"):
            try:
                preds[(r["league"], str(r["eid"]))] = json.loads(r["payload"]) if r["payload"] else None
            except Exception:
                pass
    except sqlite3.Error:
        pass
    series = {}
    try:
        for league, eid, book, mk, side, line, price, ts in c.execute(
                "SELECT league,eid,book,market,side,line,price,ts FROM lines ORDER BY ts"):
            key = (league, str(eid))
            series.setdefault(key, {"lines": {}, "splits": {}, "n_points": 0})
            series[key]["lines"].setdefault(mk, {}).setdefault(book, {}).setdefault(side, []).append([ts, line, price])
            series[key]["n_points"] += 1
        for league, eid, mk, side, t, m, ts in c.execute(
                "SELECT league,eid,market,side,tickets,money,ts FROM splits ORDER BY ts"):
            key = (league, str(eid))
            series.setdefault(key, {"lines": {}, "splits": {}, "n_points": 0})
            series[key]["splits"].setdefault(mk, {}).setdefault(side, []).append([ts, t, m])
            series[key]["n_points"] += 1
    except sqlite3.Error:
        pass
    c.close()
    rows.sort(key=lambda r: r.get("start_ts") or r.get("created_at") or 0)
    return rows, preds, series


def _apply(rows, preds, series, min_present, min_agree):
    kept, reasons = [], defaultdict(int)
    from server import core as CORE
    for r in rows:
        r = dict(r)
        if r.get("ev") is None and r.get("p_final") is not None and r.get("odds") is not None:
            try:
                r["ev"] = CORE.ev(r["p_final"], r["odds"])
            except Exception:
                pass
        pred = preds.get((r.get("league"), str(r.get("eid"))))
        ser = series.get((r.get("league"), str(r.get("eid"))))
        _, analysis = Q.reconstruct_signals(r, ser, pred)
        ok, why = Q.would_publish(r, analysis, pred, min_present=min_present, min_agree=min_agree)
        if ok:
            kept.append(r)
        else:
            reasons[why or "descartado"] += 1
    return kept, dict(reasons)


GRID = [
    dict(name="filtro_default_4y4", min_present=4, min_agree=4),
    dict(name="filtro_3y3", min_present=3, min_agree=3),
    dict(name="filtro_3y2", min_present=3, min_agree=2),
    dict(name="solo_ev_conf_y_coherencia", min_present=0, min_agree=0),
    dict(name="filtro_2y2", min_present=2, min_agree=2),
]


def _better(a, b):
    """True si a es estrictamente mejor que b en ROI, o empata ROI y mejora acierto, con muestra no ridícula."""
    if not a or not b:
        return False
    if (a.get("n_priced") or 0) < max(8, int((b.get("n_priced") or 0) * 0.15)):
        return False
    ra, rb = a.get("roi"), b.get("roi")
    if ra is None:
        return False
    if rb is None:
        return True
    if ra > rb + 0.05:
        return True
    if abs(ra - rb) <= 0.05 and (a.get("hit_rate") or 0) > (b.get("hit_rate") or 0) + 0.25:
        return True
    return False


def run(path):
    rows, preds, series = _load(path)
    base = _metrics(rows)
    n = len(rows)
    cut = max(1, int(n * 0.70))
    train, hold = rows[:cut], rows[cut:]
    variants = {}
    for g in GRID:
        kept, reasons = _apply(rows, preds, series, g["min_present"], g["min_agree"])
        ktr, _ = _apply(train, preds, series, g["min_present"], g["min_agree"])
        kho, _ = _apply(hold, preds, series, g["min_present"], g["min_agree"])
        variants[g["name"]] = dict(
            params=dict(min_present=g["min_present"], min_agree=g["min_agree"]),
            full=_metrics(kept), train=_metrics(ktr), holdout=_metrics(kho),
            n_kept=len(kept), reasons=reasons,
        )
    default = variants["filtro_default_4y4"]
    note = []
    trained_choice = "filtro_default_4y4"
    # si el default es peor que el conjunto actual EN ENTRENAMIENTO, se prueba la grilla (sólo train)
    if not _better(default["train"], _metrics(train)) and (default["train"].get("roi") is None or (_metrics(train).get("roi") is not None and default["train"]["roi"] < _metrics(train)["roi"])):
        note.append("El filtro default (≥4 presentes, ≥4 a favor) no mejora el entrenamiento frente al conjunto actual.")
        best_name, best_tr = "filtro_default_4y4", default["train"]
        for name, v in variants.items():
            if name == "filtro_default_4y4":
                continue
            if _better(v["train"], best_tr) or (best_tr.get("n_priced") in (0, None) and (v["train"].get("n_priced") or 0) > 0 and (v["train"].get("roi") or -999) > (best_tr.get("roi") or -999)):
                best_name, best_tr = name, v["train"]
        trained_choice = best_name
        note.append(f"Mejor umbral en entrenamiento (sin mirar holdout para elegir): {best_name}.")
        ho_def, ho_ch = default["holdout"], variants[best_name]["holdout"]
        note.append("Holdout del default: " + json.dumps({k: ho_def[k] for k in ("n", "hit_rate", "units", "roi", "clv") if k in ho_def}, ensure_ascii=False))
        note.append("Holdout del umbral elegido en train: " + json.dumps({k: ho_ch[k] for k in ("n", "hit_rate", "units", "roi", "clv") if k in ho_ch}, ensure_ascii=False))
        if _better(ho_ch, ho_def) or ((ho_ch.get("roi") or -999) >= (ho_def.get("roi") or -999)):
            note.append("El umbral elegido en train no se deteriora en holdout; se reporta, pero la app en vivo conserva el criterio pedido (≥4 y ≥4) salvo que se indique lo contrario.")
        else:
            note.append("El umbral elegido en train empeora en holdout: se descarta para producción (evitar sobreajuste). Se mantiene ≥4 y ≥4.")
            trained_choice = "filtro_default_4y4"
    else:
        note.append("El filtro default no es peor que el conjunto actual en entrenamiento, o no hay evidencia clara en contra. Se mantiene ≥4 y ≥4.")

    out = dict(
        db=os.path.abspath(path),
        paper_only=True,
        n_main_graded=n,
        n_train=len(train), n_holdout=len(hold),
        current_set=base,
        current_train=_metrics(train),
        current_holdout=_metrics(hold),
        variants=variants,
        chosen_for_report=trained_choice,
        notes=note,
        caveat="Las señales de lesiones, alineaciones, clima y parte de las tendencias no quedan guardadas en el histórico; en el backtest cuentan como «sin dato». Eso reduce el número de picks que pasarían el filtro de 4 señales presentes.",
    )
    return out


def _fmt(m):
    if not m:
        return "—"
    def f(x, suf=""):
        return "—" if x is None else f"{x}{suf}"
    return (f"n={m.get('n')}  acierto={f(m.get('hit_rate'), '%')}  "
            f"u={f(m.get('units'))}  ROI={f(m.get('roi'), '%')}  "
            f"CLV={f(m.get('clv'), ' pp')} (n_clv={m.get('clv_n')})")


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    path = argv[0] if argv else os.environ.get("APUESTAS_DB") or os.path.join(ROOT, "data", "history.db")
    if not os.path.exists(path):
        print(f"No existe {path}", file=sys.stderr)
        sys.exit(2)
    res = run(path)
    print("BACKTEST FILTRO DE CALIDAD (solo papel, picks principales ya calificados)")
    print(f"DB: {res['db']}")
    print(f"Muestra: {res['n_main_graded']} mains calificados  · train {res['n_train']} / holdout {res['n_holdout']}")
    print(f"Conjunto actual (todos los mains):     {_fmt(res['current_set'])}")
    print(f"  train:                               {_fmt(res['current_train'])}")
    print(f"  holdout:                             {_fmt(res['current_holdout'])}")
    for name, v in res["variants"].items():
        print(f"\n{name}  (presentes≥{v['params']['min_present']}, a_favor≥{v['params']['min_agree']}, conservados {v['n_kept']})")
        print(f"  full:    {_fmt(v['full'])}")
        print(f"  train:   {_fmt(v['train'])}")
        print(f"  holdout: {_fmt(v['holdout'])}")
        if v.get("full", {}).get("by_sport"):
            for sp, sm in v["full"]["by_sport"].items():
                print(f"    {sp}: {_fmt(sm)}")
        if v.get("reasons"):
            top = sorted(v["reasons"].items(), key=lambda x: -x[1])[:8]
            print("  motivos de descarte:", "; ".join(f"{k} ({n})" for k, n in top))
    print("\nElegido para el reporte:", res["chosen_for_report"])
    for n in res["notes"]:
        print("·", n)
    print("·", res["caveat"])
    dest = os.path.join(ROOT, "data", "backtest_quality.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nJSON: {dest}")
    return res


if __name__ == "__main__":
    main()
