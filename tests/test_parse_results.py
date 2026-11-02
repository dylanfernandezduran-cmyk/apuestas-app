"""Interpretación de resultados con respuestas REALES de ESPN (tests/fixtures, guardadas de juegos finalizados el 31-oct-2026)."""
from conftest import fixture
from server.grading import parse_team_summary, parse_tennis_event, grade_row, settle

def test_nba_final():
    r = parse_team_summary(fixture("nba_401909896.json"), home_id="26", away_id="22", family="basketball")   # Portland 112 @ Utah 90
    assert r["state"] == "final" and (r["home"], r["away"]) == (90, 112)
    assert settle("ml", "away", None, r) == "GANADO"
    assert settle("spread", "home", 21.5, r) == "PERDIDO"        # Utah +21.5 pierde por 22
    assert settle("spread", "home", 22.5, r) == "GANADO"
    assert settle("total", "over", 201.5, r) == "GANADO" and settle("total", "under", 202, r) == "PUSH"

def test_home_away_identified_by_team_id_not_order():
    # si los ids vienen invertidos respecto al orden, manda el id
    r = parse_team_summary(fixture("nba_401909896.json"), home_id="22", away_id="26", family="basketball")
    assert (r["home"], r["away"]) == (112, 90)

def test_nhl_overtime_counts_everything():
    r = parse_team_summary(fixture("nhl_ot_401892614.json"), home_id="1", away_id="4", family="hockey")   # 5-4 en OT
    assert r["state"] == "final" and (r["home"], r["away"]) == (5, 4) and "home_t" not in r
    assert settle("total", "over", 9, r) == "PUSH"       # 9 goles en total incl. OT

def test_nhl_shootout_total_excludes_shootout_goal():
    r = parse_team_summary(fixture("nhl_so_401892616.json"), home_id="27", away_id="20", family="hockey")  # home 5, away 4 (penales)
    assert (r["home"], r["away"]) == (5, 4) and (r["home_t"], r["away_t"]) == (4, 4)
    assert settle("total", "over", 8.5, r) == "PERDIDO"       # 8 goles reales, no 9
    assert settle("total", "under", 8.5, r) == "GANADO"
    assert settle("ml", "home", None, r) == "GANADO"
    r2 = parse_team_summary(fixture("nhl_so_401892589.json"), home_id="27", away_id="12", family="hockey")  # away 4, home 3
    assert (r2["home"], r2["away"], r2["home_t"], r2["away_t"]) == (3, 4, 3, 3)
    assert settle("total", "over", 6.5, r2) == "PERDIDO" and settle("total", "under", 6, r2) == "PUSH"
    assert settle("spread", "home", 1.5, r2) == "GANADO"

def test_laliga_final_1x2():
    r = parse_team_summary(fixture("laliga_401882820.json"), home_id="1538", away_id="1068", family="soccer")  # Levante 0 – Atlético 2
    assert r["state"] == "final" and (r["home"], r["away"]) == (0, 2)
    assert settle("ml", "away", None, r, three_way=True) == "GANADO"
    assert settle("ml", "draw", None, r, three_way=True) == "PERDIDO"
    assert settle("dc", "X2", None, r) == "GANADO" and settle("dc", "1X", None, r) == "PERDIDO"
    assert settle("spread", "away", -1.5, r) == "GANADO" and settle("spread", "away", -2, r) == "PUSH" and settle("spread", "away", -2.25, r) == "MEDIO_PERDIDO"
    assert settle("total", "under", 2.5, r) == "GANADO" and settle("total", "over", 1.5, r) == "GANADO" and settle("total", "over", 1.75, r) == "MEDIO_GANADO"

def _mut(fix, **chg):
    import copy; d = copy.deepcopy(fixture(fix))
    st = d["header"]["competitions"][0]["status"]["type"]; st.update(chg); return d

def test_not_final_stays_pending():
    r = parse_team_summary(_mut("nba_401909896.json", state="in", completed=False, name="STATUS_IN_PROGRESS"), "26", "22", "basketball")
    assert r["state"] == "pending"
    assert grade_row(dict(sport="nba", market="ml", selection="home", line=None, odds=-110, start_ts=0, home="a", away="b"), r) is None

def test_cancelled_is_void_and_postponed_pending():
    assert parse_team_summary(_mut("nba_401909896.json", name="STATUS_CANCELED", state="post"), "26", "22", "basketball")["state"] == "void"
    p = parse_team_summary(_mut("nba_401909896.json", name="STATUS_POSTPONED", state="pre", completed=False), "26", "22", "basketball")
    assert p["state"] == "pending" and p["postponed"]
    row = dict(sport="nba", market="ml", selection="home", line=None, odds=-110, start_ts=1000, home="a", away="b")
    assert grade_row(row, p, now=1000 + 86400) is None                          # pospuesto: sigue pendiente
    assert grade_row(row, p, now=1000 + 8 * 86400)[0] == "ANULADO"              # >7 días: anulado
    assert grade_row(row, parse_team_summary(_mut("nba_401909896.json", name="STATUS_CANCELED", state="post"), "26", "22", "basketball"))[0] == "ANULADO"

def test_soccer_extra_time_uses_90min_or_waits():
    d = _mut("laliga_401882820.json", name="STATUS_FINAL_AET", detail="AET")
    c = d["header"]["competitions"][0]["competitors"]
    for x in c: x["linescores"] = [{"value": 0}, {"value": 1}, {"value": 1}, {"value": 0}]   # 90' = 0-1 (2 tiempos), total 2 tras prórroga
    r = parse_team_summary(d, "1538", "1068", "soccer")
    assert r["state"] == "final" and (r["home"], r["away"]) == (1, 1) and "90" in r["note"]
    for x in c: x["linescores"] = []
    assert parse_team_summary(d, "1538", "1068", "soccer")["state"] == "pending"

# ---------------- tenis
def comp(cid, lg="atp"):
    return next(c for c in fixture(f"tennis_{lg}_post.json") if str(c["id"]) == str(cid))

def test_tennis_three_sets():
    r = parse_tennis_event(comp(187154), "3052", "11396")           # Sonego 6-2 3-6 6-3 Vallejo
    assert r["state"] == "final" and r["score_text"] == "6-2 3-6 6-3" and (r["sh"], r["sa"]) == (2, 1) and (r["gh"], r["ga"]) == (15, 11)
    assert settle("ml", "home", None, r) == "GANADO"
    assert settle("spread", "home", -3.5, r) == "GANADO" and settle("spread", "home", -4.5, r) == "PERDIDO"      # margen +4 juegos
    assert settle("total", "over", 25.5, r) == "GANADO" and settle("total", "over", 26.5, r) == "PERDIDO" and settle("total", "under", 26, r) == "PUSH"
    assert settle("stotal", "over", 2.5, r) == "GANADO" and settle("sspread", "away", 1.5, r) == "GANADO"

def test_tennis_swapped_players_are_handled_by_id():
    r = parse_tennis_event(comp(187154), "11396", "3052")           # misma partida con local/visitante invertidos
    assert (r["sh"], r["sa"]) == (1, 2) and (r["gh"], r["ga"]) == (11, 15) and r["score_text"] == "2-6 6-3 3-6"
    assert settle("ml", "home", None, r) == "PERDIDO" and settle("spread", "home", 4.5, r) == "GANADO" and settle("spread", "home", 3.5, r) == "PERDIDO"

def test_tennis_two_sets_and_tiebreak_set():
    r = parse_tennis_event(comp(187148), "7794", "3809")            # Neumayer 6-4 6-3 Kopriva
    assert (r["sh"], r["sa"], r["gh"], r["ga"]) == (2, 0, 12, 7)
    assert settle("sspread", "home", -1.5, r) == "GANADO" and settle("stotal", "under", 2.5, r) == "GANADO"
    r2 = parse_tennis_event(comp(187157), "8136", "7794")           # Droguet 6-7 3-6 Neumayer (set con tie-break 7-6)
    assert r2["state"] == "final" and (r2["gh"], r2["ga"]) == (9, 13) and (r2["sh"], r2["sa"]) == (0, 2)

def test_tennis_walkover_is_void():
    r = parse_tennis_event(comp(187155), "3811", "9213")
    assert r["state"] == "void"
    row = dict(sport="tenis", market="ml", selection="home", line=None, odds=-200, start_ts=0, home="Machac", away="Marozsan")
    assert grade_row(row, r)[0] == "ANULADO"

def test_tennis_not_finished_pending():
    c = __import__("copy").deepcopy(comp(187154)); c["status"]["type"].update(state="in", name="STATUS_IN_PROGRESS")
    assert parse_tennis_event(c, "3052", "11396")["state"] == "pending"

def test_all_real_tennis_finals_are_consistent():
    """Todos los finales reales de la fixture (ATP+WTA): los sets ganados cuadran con el ganador de ESPN y las sumas con los marcadores."""
    n = 0
    for lg in ("atp", "wta"):
        for c in fixture(f"tennis_{lg}_post.json"):
            a, b = c["competitors"]
            r = parse_tennis_event(c, a["id"], b["id"])
            if r["state"] != "final": continue
            n += 1
            assert (r["sh"] > r["sa"]) == bool(a["winner"])
            assert r["gh"] == sum(int(x["value"]) for x in a["linescores"]) and r["ga"] == sum(int(x["value"]) for x in b["linescores"])
            assert settle("ml", "home", None, r) == ("GANADO" if a["winner"] else "PERDIDO")
    assert n >= 15
