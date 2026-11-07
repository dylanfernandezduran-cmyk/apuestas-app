"""Tickets / parlays de papel: avisos, combinados, guardado, calificación pierna por pierna."""
import asyncio
from server import tickets as T, history

NOW = 1_900_000_000
def leg(eid="1", market="ml", sel="home", odds=-110, p=.6, line=None, label=None, start=NOW + 3600, kind="game", **kw):
    d = dict(kind=kind, league="nba", eid=eid, sport="nba", start_ts=start, home="Utah", away="Portland", home_id="26", away_id="22",
             market=market, selection=sel, line=line, odds=odds, label=label or f"{market} {sel} {eid}", p=p)
    d.update(kw); return d

def test_check_contradiction_and_correlation():
    assert T.check([leg(), leg(sel="away")])["errors"]                                   # mismo mercado, lados opuestos
    c = T.check([leg(), leg(market="spread", line=-3.5)])
    assert not c["errors"] and any("Correlacionadas" in w for w in c["warnings"])
    c = T.check([leg(), leg(eid="2")])
    assert c == dict(errors=[], warnings=[])

def test_combine_odds_and_prob():
    cb = T.combine([leg(odds=-110, p=.6), leg(eid="2", odds=+150, p=.45)])
    assert abs(cb["dec"] - (1 + 100 / 110) * 2.5) < 1e-3 and abs(cb["p_model"] - .27) < 1e-9 and cb["american"] > 0

def test_create_rejects_started_and_saves(db):
    T.reset_for_tests()
    assert not T.create([leg(start=NOW - 5)], now=NOW)["ok"]
    r = T.create([leg(), leg(eid="2")], name="Prueba", now=NOW)
    assert r["ok"] and r["id"]
    d = T.by_day(r and __import__("server.record", fromlist=["x"]).cdmx_date(NOW + 3600))
    assert d["tickets"][0]["name"] == "Prueba" and d["summary"]["pending"] == 1

def test_settle_ticket_rules():
    w = lambda s, o=-110: dict(status=s, odds=o)
    assert T.settle_ticket([w("GANADO"), w("PERDIDO")])[0] == "PERDIDO"
    assert T.settle_ticket([w("GANADO"), w("PENDIENTE")])[0] == "PENDIENTE"
    assert T.settle_ticket([w("PERDIDO"), w("PENDIENTE")])[0] == "PERDIDO"           # ya perdió aunque falte una
    assert T.settle_ticket([w("PUSH"), w("ANULADO")]) == ("PUSH", 1.0)
    st, m = T.settle_ticket([w("GANADO", +100), w("PUSH")]); assert st == "GANADO" and abs(m - 2) < 1e-9

def test_grade_pending_uses_real_result(db, monkeypatch):
    T.reset_for_tests()
    r = T.create([leg(), leg(eid="2", market="total", sel="over", line=200.5)], now=NOW)
    from server import grading as G
    async def fake(row):
        return dict(state="final", home=110, away=100) if row["eid"] == "1" else dict(state="final", home=90, away=100)
    monkeypatch.setattr(G, "fetch_result", fake)
    asyncio.run(T.grade_pending(now=NOW + 99999))
    t = T._rows("SELECT * FROM tickets WHERE id=?", (r["id"],))[0]
    assert [l["status"] for l in t["legs"]] == ["GANADO", "PERDIDO"] and t["status"] == "PERDIDO" and t["units"] == -1
