"""Demostración/verificación de la calificación con juegos YA TERMINADOS reales (ESPN).
Crea picks SINTÉTICOS (source='demo', NO son picks reales del modelo) sobre finales de ayer en una BD aparte (por defecto data/demo.db),
corre grading.grade_pending() contra ESPN en vivo y compara contra un cálculo independiente del marcador.
Uso: APUESTAS_DB=data/demo.db python scripts/demo_grade_finals.py [YYYYMMDD]"""
import os, sys, asyncio, time, json
os.environ.setdefault("APUESTAS_DB", os.path.join(os.path.dirname(__file__), "..", "data", "demo.db"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import httpx
from server import record as R, grading as G, history
from server.config import ESPN, LEAGUES

day = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y%m%d", time.localtime(time.time() - 86400))
J = lambda u, **p: httpx.get(u, params=p, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).json()
TOT = {"nba": 215.5, "nhl": 5.5, "esp.1": 2.5, "mex.1": 2.5, "nfl": 44.5}
SPR = {"nba": -2.5, "nhl": -1.5, "esp.1": -0.25, "mex.1": -0.75, "nfl": -3.5}
rows, expect = [], {}
now = int(time.time())
def add(lg, ev, c, home, away, h, a):
    base = dict(sport=LEAGUES[lg]["sport"], league=lg, eid=str(ev), start_ts=now - 86400, home=home["n"], away=away["n"], home_id=str(home["id"]), away_id=str(away["id"]),
                created_at=now - 90000, source="demo", basis="modelo", p_model=.55, p_final=.55, p_nv=.52, edge=.03, book="DEMO")
    return base
from datetime import datetime
for lg in ("nba", "nhl", "esp.1", "mex.1"):
    d = J(f"{ESPN}/{LEAGUES[lg]['path']}/scoreboard", dates=day)
    for e in d.get("events", []):
        c = e["competitions"][0]
        if c["status"]["type"]["name"] not in ("STATUS_FINAL", "STATUS_FULL_TIME"): continue
        H = next(x for x in c["competitors"] if x["homeAway"] == "home"); A = next(x for x in c["competitors"] if x["homeAway"] == "away")
        home = dict(id=H["team"]["id"], n=H["team"]["displayName"]); away = dict(id=A["team"]["id"], n=A["team"]["displayName"])
        det = c["status"]["type"].get("detail", "")
        h, a = int(float(H["score"])), int(float(A["score"]))
        so = det.endswith("SO")
        base = add(lg, e["id"], c, home, away, h, a)
        for mk, sel, line, typ, odds in (("ml", "home", None, "main", -120), ("spread", "home", SPR[lg], "suggestion", -110), ("total", "over", TOT[lg], "suggestion", -105)):
            rows.append(dict(base, market=mk, selection=sel, line=line, type=typ, odds=odds, label=f"{home['n']} ML" if mk == "ml" else (f"{home['n']} {SPR[lg]:+g}" if mk == "spread" else f"Over {TOT[lg]:g}")))
            # esperado independiente (sin usar grading.settle)
            tot = h + a - (1 if so else 0) if mk == "total" else None
            if mk == "ml": exp = "GANADO" if h > a else "PERDIDO" if h < a else ("PERDIDO" if lg in ("esp.1", "mex.1") else "PUSH")
            elif mk == "spread":
                m = h - a; L = SPR[lg]
                parts = [L - .25, L + .25] if abs(L * 4 % 2) == 1 else [L]
                sc = sum((1 if m + p > 0 else -1 if m + p < 0 else 0) for p in parts) / len(parts)
                exp = {1: "GANADO", .5: "MEDIO_GANADO", 0: "PUSH", -.5: "MEDIO_PERDIDO", -1: "PERDIDO"}[sc]
            else: exp = "GANADO" if tot > TOT[lg] else "PERDIDO"
            expect[(lg, str(e["id"]), mk)] = (exp, f"{away['n']} {a} @ {home['n']} {h}" + (" (SO)" if so else ""))
# tenis: finales del scoreboard
for lg in ("atp",):
    d = J(f"{ESPN}/{LEAGUES[lg]['path']}/scoreboard")
    n = 0
    for e in d.get("events", []):
        for gr in e.get("groupings", []):
            if "Singles" not in gr["grouping"]["displayName"]: continue
            for c in gr["competitions"]:
                if c["status"]["type"]["name"] != "STATUS_FINAL" or n >= 8: continue
                A, B = c["competitors"][0], c["competitors"][1]
                sa = [int(x["value"]) for x in A["linescores"]]; sb = [int(x["value"]) for x in B["linescores"]]
                if any(max(x, y) > 7 for x, y in zip(sa, sb)): continue
                n += 1
                base = dict(sport="tenis", league=lg, eid=str(c["id"]), start_ts=now - 86400, home=A["athlete"]["displayName"], away=B["athlete"]["displayName"], home_id=str(A["id"]), away_id=str(B["id"]),
                            created_at=now - 90000, source="demo", basis="mercado", p_model=None, p_final=None, p_nv=.55, edge=None, book="DEMO")
                gh, ga = sum(sa), sum(sb); ssa = sum(x > y for x, y in zip(sa, sb)); ssb = len(sa) - ssa
                for mk, sel, line, typ, odds, lab in (("ml", "home", None, "main", -150, f"{base['home']} ML"), ("spread", "home", -3.5, "suggestion", -110, f"{base['home']} -3.5 juegos"),
                                                      ("total", "under", 22.5, "suggestion", -115, "Under 22.5 juegos"), ("sspread", "home", -1.5, "suggestion", 120, f"{base['home']} -1.5 sets"), ("stotal", "over", 2.5, "suggestion", 105, "Over 2.5 sets")):
                    rows.append(dict(base, market=mk, selection=sel, line=line, type=typ, odds=odds, label=lab))
                    exp = {"ml": "GANADO" if ssa > ssb else "PERDIDO", "spread": "GANADO" if gh - ga - 3.5 > 0 else "PERDIDO", "total": "GANADO" if gh + ga < 22.5 else "PERDIDO",
                           "sspread": "GANADO" if ssa - ssb - 1.5 > 0 else "PERDIDO", "stotal": "GANADO" if ssa + ssb > 2.5 else "PERDIDO"}[mk]
                    expect[(lg, str(c["id"]), mk)] = (exp, " ".join(f"{x}-{y}" for x, y in zip(sa, sb)))
inserted = R.record_rows(rows)
print("picks demo insertados:", inserted, "BD:", history.PATH)
t = time.time(); out = asyncio.run(G.grade_pending(now=time.time())); print("grade_pending:", out, f"{time.time()-t:.1f}s")
bad = 0
for r in R.query(limit=1000):
    exp = expect.get((r["league"], r["eid"], r["market"]))
    ok = exp and exp[0] == r["status"]
    if not ok: bad += 1
    print("OK " if ok else "MAL", f"{r['league']:5} {r['market']:7} {r['label'][:34]:34} {r['status']:13} {R.profit(r['status'], r['odds']) if r['units'] is None else r['units']!s:>7}  {r['score_text'] or ''}")
print("pendientes:", sum(1 for r in R._rows("SELECT * FROM picks WHERE status='PENDIENTE'")), "· discrepancias:", bad)
sys.exit(1 if bad else 0)
