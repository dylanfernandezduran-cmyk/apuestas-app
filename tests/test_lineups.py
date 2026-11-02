"""Alineaciones: titulares reales (resúmenes ESPN guardados), cambios vs foto previa en SQLite, rotulado confirmada/proyectada."""
from conftest import fixture
from server import lineups as L

def test_nba_starters_real_summary():
    r = L.starters_from_summary(fixture("lineup_nba.json"), "basketball", "26")
    assert len(r["players"]) == 5 and all(p["id"] and p["name"] for p in r["players"]) and r["players"][0]["name"] == "Lauri Markkanen"
    assert L.starters_from_summary(fixture("lineup_nba.json"), "basketball", "9999") is None

def test_soccer_xi_and_formation():
    r = L.starters_from_summary(fixture("lineup_soccer.json"), "soccer", "1538")
    assert len(r["players"]) == 11 and r["formation"] == "4-2-3-1"

def test_nhl_goalie():
    r = L.starters_from_summary(fixture("lineup_nhl.json"), "hockey", "27")
    assert r["goalie"]["name"] == "Juuse Saros" and r["players"] == []

def test_no_starters_when_not_published():
    s = fixture("lineup_soccer.json"); s["rosters"] = []
    assert L.starters_from_summary(s, "soccer", "1538") is None
    assert L.starters_from_summary({}, "basketball", "26") is None

def P(i, n, pos): return dict(id=str(i), name=n, pos=pos)

def test_diff_enters_for_same_position_and_leaves():
    old = [P(1, "A", "G"), P(2, "B", "F"), P(3, "C", "C")]
    ch = L.diff(old, [P(1, "A", "G"), P(9, "Z", "F"), P(3, "C", "C")])
    assert ch == [dict(kind="cambio", enters="Z", leaves="B", pos="F")]
    ch2 = L.diff(old, [P(1, "A", "G"), P(2, "B", "F")])
    assert ch2 == [dict(kind="sale", enters=None, leaves="C", pos="C")]
    assert L.diff(old, old) == [] and L.diff(None, old)[0]["kind"] == "cambio"

def test_track_reports_changes_only_vs_previous_snapshot(db):
    a = [P(1, "A", "G"), P(2, "B", "F")]
    assert L.track("nba", "e1", "t1", "proyectada", a, now=1000) == ([], None)          # primera foto: nada que comparar
    assert L.track("nba", "e1", "t1", "proyectada", a, now=2000) == ([], None)          # igual: sin cambios
    b = [P(1, "A", "G"), P(3, "C", "F")]
    ch, ts = L.track("nba", "e1", "t1", "confirmada", b, now=3000)
    assert ts == 1000 and ch[0]["enters"] == "C" and ch[0]["leaves"] == "B" and ch[0]["vs"] == "proyectada"
    # otro partido/equipo no se mezcla
    assert L.track("nba", "e2", "t1", "confirmada", b, now=4000) == ([], None)
