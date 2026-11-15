#!/usr/bin/env python3
"""Walk-forward honesto: filtro viejo (picks main ya registrados) vs filtro nuevo
(coherencia predicción + EV>0 reconstruible + bloqueo de segmentos del récord pasado).

El filtro en vivo también exige 4 señales y confianza Media/Alta; esas columnas
casi no se guardaron en el histórico, así que ese tramo no se puede backtestear
por completo (un intento previo dejó 0 picks). Aquí sólo se mide lo reconstruible.
Nada se inventa y no se reescribe la base.

Uso: python scripts/backtest_learn.py [db1] [db2...]
"""
from __future__ import annotations
import json, os, sqlite3, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server import learn, quality as Q

DONE = ("GANADO", "PERDIDO", "PUSH", "MEDIO_GANADO", "MEDIO_PERDIDO")


def _load(paths):
    picks, preds = {}, {}
    for path in paths:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        for r in c.execute("SELECT * FROM picks WHERE start_ts>100000"):
            r = dict(r)
            key = (r["league"], str(r["eid"]), r["market"], r["selection"], r.get("type") or "")
            prev = picks.get(key)
            score = (1 if r.get("status") in DONE else 0, r.get("graded_at") or 0, r.get("updated_at") or 0, r.get("created_at") or 0)
            if prev is None or score > prev["_score"]:
                r["_score"] = score
                picks[key] = r
        for r in c.execute("SELECT * FROM predictions"):
            r = dict(r)
            key = (r["league"], str(r["eid"]))
            ts = r.get("updated_at") or r.get("created_at") or 0
            prev = preds.get(key)
            if prev is None or ts >= (prev.get("updated_at") or prev.get("created_at") or 0):
                try:
                    r["pred"] = json.loads(r.pop("payload") or "{}")
                except Exception:
                    r["pred"] = {}
                preds[key] = r
        c.close()
    rows = [r for r in picks.values() if r.get("type") == "main" and r.get("status") in DONE]
    rows.sort(key=lambda r: (r.get("start_ts") or 0, r.get("id") or 0))
    return rows, preds


def _consistent(pick, pred_row):
    if not pred_row or not pred_row.get("pred"):
        return False, "sin predicción guardada"
    cand = dict(market={"ml": "ML", "spread": "Spread", "total": "Total", "btts": "BTTS"}.get(pick.get("market"), pick.get("market")),
                side=pick.get("selection"), line=pick.get("line"))
    fam = "soccer" if pick.get("sport") == "futbol" else ("tennis" if pick.get("sport") == "tenis" else pick.get("sport"))
    if not Q.same_pick(pred_row["pred"], cand, fam):
        return False, "contradice la predicción (lado o línea)"
    return True, None


def decide_new(pick, pred, train):
    ok, reason = _consistent(pick, pred)
    if not ok:
        return False, reason
    ev = learn.ev_of(pick)
    if ev is None:
        return False, "EV: sin dato"
    if ev <= 0:
        return False, "EV no positivo"
    segs = learn.build_segments(train, min_n=learn.MIN_N).get("segments")
    fb = learn.feedback(pick, segs)
    if fb.get("action") == "block":
        return False, fb.get("reason") or "segmento negativo"
    if fb.get("action") == "stricter":
        if ev < 5:
            return False, "segmento flojo y EV < 5%"
        if (pick.get("conf_level") or "") != "Alta":
            # confianza no guardada en la mayoría: no se relaja el umbral; se descarta
            return False, "segmento flojo y confianza no es Alta"
    return True, None


def picks_per_day(rows):
    if not rows:
        return 0.0
    days = sorted({int(r["start_ts"] // 86400) for r in rows if r.get("start_ts")})
    if not days:
        return 0.0
    span = days[-1] - days[0] + 1
    return round(len(rows) / max(span, 1), 2)


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    paths = argv or [
        os.path.join(ROOT, "data", "history.db"),
        "/tmp/nrnm-audit/history-pc-live.db",
        "/tmp/nrnm-audit/history.db",
    ]
    paths = [p for p in paths if os.path.isfile(p)]
    rows, preds = _load(paths)
    old = learn.summarize(rows)
    pred_map = {(r["league"], str(r["eid"])): r for r in preds.values()} if preds else {}
    # also index preds loaded as dicts from _load
    pmap = {}
    for k, v in preds.items():
        pmap[k] = v
    wf = learn.walk_forward(rows, pmap, lambda r, pred, train: decide_new(r, pred, train),
                            week_secs=7 * 86400, min_train=learn.MIN_N)
    new_rows = wf["kept"]
    new = learn.summarize(new_rows)
    # also: consistency+EV without segment (diagnostic)
    cons = []
    reasons = defaultdict(int)
    for r in rows:
        ok, reason = decide_new(r, pmap.get((r.get("league"), str(r.get("eid")))), [])  # empty train → no block
        # wait, empty train segments won't block; ev+consistency only
        okc, rsc = _consistent(r, pmap.get((r.get("league"), str(r.get("eid")))))
        ev = learn.ev_of(r)
        if not okc:
            reasons[rsc] += 1
            continue
        if ev is None:
            reasons["EV: sin dato"] += 1
            continue
        if ev <= 0:
            reasons["EV no positivo"] += 1
            continue
        cons.append(r)
    mid = learn.summarize(cons)

    out = dict(
        dbs=paths,
        paper_only=True,
        note=("Filtro viejo = picks principales ya registrados y calificados. "
              "Filtro nuevo (walk-forward) = coherencia con la predicción + EV>0 reconstruible "
              "+ bloqueo de segmentos con n≥30 e IC de ROI significativamente negativo, "
              "aprendidos sólo con el pasado. El filtro en vivo también exige 4 señales y "
              "confianza Media/Alta, no backtesteable por completo porque esas columnas casi no se guardaron. "
              "Nada de esto es una promesa de acierto (un 80% no está respaldado por el récord)."),
        old=dict(**old, picks_per_day=picks_per_day(rows)),
        new_walk_forward=dict(**new, picks_per_day=picks_per_day(new_rows),
                              n_old=wf["n_old"], n_new=wf["n_new"], folds=len(wf["folds"])),
        new_consistency_and_ev=dict(**mid, picks_per_day=picks_per_day(cons), drop_reasons=dict(reasons)),
        folds=[{k: (v if k != "window" else v) for k, v in f.items() if k not in ("window",)}
               | dict(window_start=f["window"][0], window_end=f["window"][1])
               for f in wf["folds"]],
    )
    dest = os.path.join(ROOT, "data", "backtest_learn.json")
    json.dump(out, open(dest, "w"), ensure_ascii=False, indent=2)
    def fmt(m, label):
        print(f"  {label}: n={m.get('n')} acierto={m.get('hit')}%  ROI={m.get('roi')}%  "
              f"CLV={m.get('clv')} (n_clv={m.get('n_clv')})  u={m.get('units')}  "
              f"picks/día={m.get('picks_per_day')}")
    print("BACKTEST (paper, sin inventar)")
    print("DBs:", ", ".join(paths))
    fmt({**old, "picks_per_day": picks_per_day(rows)}, "VIEJO (mains calificados)")
    fmt({**mid, "picks_per_day": picks_per_day(cons)}, "NUEVO coherencia+EV (todo el set, no walk-forward)")
    fmt({**new, "picks_per_day": picks_per_day(new_rows)}, "NUEVO walk-forward (coherencia+EV+segmentos)")
    print("Motivos de descarte (coherencia+EV):", dict(reasons))
    print("escrito", dest)
    return out


if __name__ == "__main__":
    main()
