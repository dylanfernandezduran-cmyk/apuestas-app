"""Registro de picks (SQLite temporal): dedupe, primera línea/cuota, un principal, nada después del inicio, calificación y P&L."""
import asyncio, time
from datetime import datetime, timezone
from conftest import fixture
from server import record as R, grading as G, history

NOW = 1_800_000_000
def iso(ts): return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

def analysis(start=NOW + 3600, state="pre", lean_odds=-110, spread_line=-3.5, spread_price=-105, lean_side="home", eid="1", league="nba"):
    g = dict(sport="nba", league=league, id=eid, state=state, date=iso(start), home=dict(id="26", name="Utah"), away=dict(id="22", name="Portland"))
    lean = dict(market="ML", side=lean_side, line=None, label=f"{'Utah' if lean_side=='home' else 'Portland'} ML", price=lean_odds, p_model=.6, p_final=.58, p_nv=.55, edge=.03, status="PICK")
    probs = dict(markets=[
        dict(key="ml", title="Ganador", unit=None, outcomes=[dict(key="ml.home", side="home", p_model=.6, p_final=.58, p_nv=.55, p_pin=None, edge=.03, best=dict(price=lean_odds, book="Pinnacle"), clipped=False, label="Utah ML", line=None)]),
        dict(key="spread", title="Spread", unit=None, outcomes=[dict(key="spread.home", side="home", p_model=.52, p_final=.52, p_nv=.5, p_pin=None, edge=.01, best=dict(price=spread_price, book="Pinnacle"), clipped=False, label=f"Utah {spread_line}", line=spread_line)]),
    ])
    return dict(game=g, odds=dict(book="ESPN BET"), picks=dict(lean=lean, candidates=[lean]), probs=probs)

def test_records_main_and_suggestions(db):
    n = R.record_analysis(analysis(), now=NOW)
    rows = R.game_rows("nba", "1")
    assert n == len(rows) >= 2
    main = [r for r in rows if r["type"] == "main"]
    assert len(main) == 1 and main[0]["market"] == "ml" and main[0]["selection"] == "home" and main[0]["odds"] == -110 and main[0]["status"] == "PENDIENTE"
    sp = next(r for r in rows if r["market"] == "spread")
    assert sp["type"] == "suggestion" and sp["line"] == -3.5 and sp["odds"] == -105 and sp["book"] == "Pinnacle"
    assert all(r["start_ts"] == NOW + 3600 and r["home"] == "Utah" and r["away"] == "Portland" and r["source"] == "live" for r in rows)

def test_dedupe_and_first_line_odds_are_kept(db):
    R.record_analysis(analysis(), now=NOW)
    n0 = len(R.game_rows("nba", "1"))
    # se vuelve a analizar con otra línea/cuota: no se duplica y NO se sobrescribe lo primero registrado
    assert R.record_analysis(analysis(lean_odds=-130, spread_line=-5.5, spread_price=-120), now=NOW + 600) == 0
    rows = R.game_rows("nba", "1")
    assert len(rows) == n0
    assert next(r for r in rows if r["market"] == "ml")["odds"] == -110
    sp = next(r for r in rows if r["market"] == "spread")
    assert (sp["line"], sp["odds"]) == (-3.5, -105)

def test_one_main_and_one_side_per_market(db):
    R.record_analysis(analysis(), now=NOW)
    R.record_analysis(analysis(lean_side="away"), now=NOW + 60)        # el modelo cambia de lado en ML: no se registra el lado contrario
    rows = R.game_rows("nba", "1")
    assert len([r for r in rows if r["type"] == "main"]) == 1
    assert [r["selection"] for r in rows if r["market"] == "ml"] == ["home"]

def test_nothing_recorded_after_start_or_for_live_games(db):
    assert R.record_analysis(analysis(start=NOW - 10), now=NOW) == 0                  # ya empezó (hora)
    assert R.record_analysis(analysis(state="in"), now=NOW) == 0                      # en vivo
    assert R.record_analysis(analysis(state="post"), now=NOW) == 0
    assert R.game_rows("nba", "1") == []

def test_grade_end_to_end_with_real_final(db, monkeypatch):
    """Portland 112 @ Utah 90 (fixture real): Utah ML pierde; Utah -3.5 pierde; Utah +21.5 gana; Over 201.5 gana."""
    a = analysis(eid="401909896", start=NOW + 3600)
    R.record_analysis(a, now=NOW)
    rows = R.game_rows("nba", "401909896")
    assert R.pending(NOW + 10) == []                                    # aún no empezó: no se califica
    summ = fixture("nba_401909896.json")
    async def fake(row): return G.parse_team_summary(summ, row["home_id"], row["away_id"], "basketball")
    monkeypatch.setattr(G, "fetch_result", fake)
    out = asyncio.run(G.grade_pending(now=NOW + 7200))
    assert out["graded"] == len(rows) and out["still_pending"] == 0
    got = {(r["market"], r["selection"]): r for r in R.game_rows("nba", "401909896")}
    ml = got[("ml", "home")]
    assert ml["status"] == "PERDIDO" and ml["units"] == -1.0 and "Portland 112 @ Utah 90" in ml["score_text"]
    assert got[("spread", "home")]["status"] == "PERDIDO"
    # no se vuelve a calificar ni se pisa
    assert asyncio.run(G.grade_pending(now=NOW + 9000))["checked"] == 0

def test_pending_stays_pending_until_final(db, monkeypatch):
    R.record_analysis(analysis(), now=NOW)
    async def fake(row): return dict(state="pending", note=None)
    monkeypatch.setattr(G, "fetch_result", fake)
    out = asyncio.run(G.grade_pending(now=NOW + 7200))
    assert out["graded"] == 0 and out["still_pending"] >= 2
    assert all(r["status"] == "PENDIENTE" and r["units"] is None for r in R.game_rows("nba", "1"))

def test_profit():
    assert R.profit("GANADO", -110) == round(100 / 110, 4) and R.profit("GANADO", 150) == 1.5
    assert R.profit("PERDIDO", 150) == -1.0 and R.profit("PUSH", -110) == 0.0
    assert R.profit("MEDIO_GANADO", 100) == 0.5 and R.profit("MEDIO_PERDIDO", 100) == -0.5
    assert R.profit("GANADO", None) is None and R.profit("ANULADO", -110) is None and R.profit("PENDIENTE", -110) is None

def test_summary_and_filters(db):
    with history._lock:
        c = R._c()
        base = dict(sport="nba", league="nba", start_ts=NOW, home="A", away="B", home_id="1", away_id="2", line=None, label="x", p_model=.5, p_final=.5, p_nv=.5, edge=0, basis="modelo", created_at=NOW, source="live")
        def add(eid, typ, st, odds, sport="nba", league="nba", sel="home"):
            d = dict(base, eid=eid, type=typ, odds=odds, sport=sport, league=league, market="ml", selection=sel, book="P")
            c.execute(f"INSERT INTO picks({R.COLS}) VALUES ({','.join('?'*22)})", tuple(d[k] for k in R.COLS.split(",")))
            c.execute("UPDATE picks SET status=?, units=? WHERE eid=? AND league=?", (st, R.profit(st, odds), eid, league))
        add("1", "main", "GANADO", 150); add("2", "main", "PERDIDO", -110); add("3", "suggestion", "PUSH", -110)
        add("4", "suggestion", "GANADO", -200, sport="tenis", league="atp"); add("5", "main", "PENDIENTE", -110); add("6", "main", "ANULADO", -110)
        add("7", "suggestion", "MEDIO_GANADO", 100)
        c.commit()
    s = R.summary()
    assert (s["W"], s["L"], s["P"]) == (2.5, 1.0, 1.5)
    assert s["pending"] == 1 and s["void"] == 1 and s["graded"] == 5
    assert abs(s["units"] - (1.5 - 1 + 0 + 0.5 + 0.5)) < 1e-6
    assert R.summary(typ="main")["graded"] == 2 and R.summary(typ="main")["units"] == 0.5
    assert R.summary(sport="tenis")["graded"] == 1 and R.summary(sport="tenis")["win_pct"] == 100.0
    assert len(R.query(limit=50)) == 5 and len(R.query(sport="nba", typ="suggestion")) == 2
