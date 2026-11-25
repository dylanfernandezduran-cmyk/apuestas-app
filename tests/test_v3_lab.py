from server import advanced as ADV, consensus as CONS, board, validation as VAL

HTML = '''<table><tr><th>x</th></tr><tr>
<td><span class="covers-CoversConsensus-table--teamBlock"><img alt="L.A. Clippers Clippers Picks" src="https://img.covers.com/covers/data/new_logos/nba/lac.png"></span>
<span><img alt="Memphis Grizzlies Picks" src="https://img.covers.com/covers/data/new_logos/nba/mem.png"></span></td>
<td>Wed. Nov 25<br />8:00 pm ET</td><td><span>30%</span><br /><span>70%</span></td><td>+7.5<br />-7.5</td><td>107<br />254</td>
<td><a href="/consensus/matchupconsensusdetails/abc">Details</a></td></tr></table>'''

def test_covers_parse_and_day():
    r = CONS.parse(HTML)
    assert len(r) == 1 and r[0]["away"]["abbr"] == "lac" and r[0]["home"]["pct"] == 70 and r[0]["home"]["picks"] == 254
    assert r[0]["url"].endswith("/abc")
    assert CONS._day_ok("Wed. Nov 25 8:00 pm ET", "2026-11-26T01:00Z") and not CONS._day_ok("Thu. Nov 26 8:00 pm ET", "2026-11-26T01:00Z")
    assert CONS._same(r[0]["home"], {"abbr": "MEM", "name": "Memphis Grizzlies"})

def test_advanced_formulas():
    st = dict(avgFieldGoalsAttempted=90.0, avgFieldGoalsMade=41.0, avgThreePointFieldGoalsMade=14.0, avgFreeThrowsAttempted=26.0,
              avgPoints=117.0, avgOffensiveRebounds=12.0, avgTurnovers=16.0, gamesPlayed=17)
    o = ADV.compute(st, opp_ppg=115.0)
    poss = 90 - 12 + 16 + 0.44 * 26
    assert o["efg"] == round(100 * (41 + 7) / 90, 1) and o["pace"] == round(poss, 1)
    assert o["ortg"] == round(11700 / poss, 1) and o["drtg"] == round(11500 / poss, 1) and o["net"] == round(o["ortg"] - o["drtg"], 1)
    assert ADV.compute({})["efg"] is None  # sin datos -> None, nada inventado

def test_monthly_series():
    rows = [dict(status="GANADO", odds=100, start_ts=1795000000), dict(status="PERDIDO", odds=-110, start_ts=1795000000),
            dict(status="GANADO", odds=None, start_ts=1795000000)]
    m = board.monthly(rows)
    assert len(m) == 1 and m[0]["n"] == 2 and m[0]["W"] == 1 and m[0]["units"] == 0.0

def test_validation_states():
    base = dict(game=dict(sport="nba", state="pre"), odds={"ml": {"home": -110}}, model={"sample": 0.9})
    v = VAL.validate(dict(base, picks={"lean": {"label": "x", "ev": -0.02}}))
    assert v["state"] == "PASAR"

def test_policy_tiers_and_locks(monkeypatch):
    from server import policy as P, quality as Q
    assert P.tier(0.45)["key"] == "bloqueado" and P.tier(0.55)["key"] == "moderada" and P.tier(0.65)["key"] == "favorable"
    assert P.tier(0.75)["key"] == "elevada" and P.tier(0.85)["key"] == "muy_elevada" and P.tier(0.93)["key"] == "auditoria"
    H = dict(n={("nba", "ml"): 100}, cal={"60–70%": dict(n=100, real=60.0, pred=65.0)})
    ok = P.check(dict(p_final=55.0, ev_pct=3.0, sport="nba", market="ml"), H)
    assert ok["approved"] and not ok["locks"]
    low = P.check(dict(p_final=0.47, ev_pct=5.0, sport="nba", market="ml"), H)
    assert not low["approved"] and [l["key"] for l in low["locks"]] == ["prob"]
    cal = P.check(dict(p_final=0.66, ev_pct=5.0, sport="nba", market="ml"), H)
    assert [l["key"] for l in cal["locks"]] == ["calibration"]
    few = P.check(dict(p_final=0.55, ev_pct=-1, sport="nhl", market="total", live=True), H)
    assert {"value", "model", "live"} <= {l["key"] for l in few["locks"]}
    aud = P.check(dict(p_final=0.95, ev_pct=2, sport="nba", market="ml"), H)
    assert [l["key"] for l in aud["locks"]] == ["audit"]
    assert Q.policy_block({"p_final": 0.48}).startswith("Bloqueado") and Q.policy_block({"p_final": 0.55}) is None
    assert Q.policy_block({"p_final": 0.91}).startswith("Auditor")
    assert P.config()["min_prob"] == 0.50
