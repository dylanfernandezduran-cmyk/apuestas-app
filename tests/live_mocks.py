"""Payloads /api/game SIMULADOS (mock) para pruebas visuales/e2e de la cancha en vivo y de la Predicción NRNM. No son datos reales."""
import copy, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FX = os.path.join(os.path.dirname(__file__), "fixtures")
_load = lambda n: json.load(open(os.path.join(FX, n)))

def _live(d, status, hs, as_, live):
    d = copy.deepcopy(d); g = d["game"]
    g["state"] = "in"; g["status"] = status; g["home"]["score"] = hs; g["away"]["score"] = as_
    d["live"] = {**dict(state="in", text=status, linescores=None, stats=[], plays=[], situation=None), **live}
    return d

def soccer():
    return _live(_load("game_soc_mex1.json"), "67'", "2", "1", dict(plays=[dict(text="Gol de Necaxa (MOCK).", clock="64'", scoring=True, kind="goal"), dict(text="Tarjeta amarilla (MOCK).", clock="51'", scoring=False, kind="yellow-card")]))

def nfl():
    d = _load("game_nfl.json"); g = d["game"]
    return _live(d, "Q3 5:32", "17", "13", dict(plays=[dict(text="(5:32 - 3rd) Pase corto completo por el centro para 7 yardas (MOCK).", clock="5:32", period="3", scoring=False)],
              situation=dict(text="Posesión · 2º y 7", possession=str(g["home"]["id"]), red_zone=False, down=2, distance=7, yard_team=g["home"].get("abbr"), yard=35, last_play=None)))

def _as(d, sport, league, name):
    d["game"].update(sport=sport, league=league, league_name=name); return d

def mlb():
    d = _live(_load("game_nfl.json"), "Alta 5ª", "3", "2", dict(plays=[dict(text="Ponche abanicando (MOCK).", clock="", period="5", scoring=False)],
              situation=dict(text="1 out · cuenta 2-1 · corredores en 1ª y 3ª", outs=1, balls=2, strikes=1, bases=[True, False, True], batter="Bateador Mock", pitcher="Lanzador Mock", last_play=None)))
    return _as(d, "mlb", "mlb", "MLB")

def nba(): return _as(_live(_load("game_nfl.json"), "Q3 5:32", "78", "81", dict(plays=[dict(text="Triple desde la esquina (MOCK).", clock="5:41", period="3", scoring=True)])), "nba", "nba", "NBA")
def nhl(): return _as(_live(_load("game_nfl.json"), "P2 8:10", "2", "1", dict(plays=[dict(text="Tiro bloqueado (MOCK).", clock="8:12", period="2", scoring=False)])), "nhl", "nhl", "NHL")

def tennis(server="home", state="in"):
    P = lambda i, n, s, sets, rk: dict(id=i, name=n, short=s, abbr=None, logo=None, flag=None, country=None, rank=rk, points=3000 - rk * 100, score=None, winner=False, sets=sets, record=f"#{rk} ATP/WTA")
    g = dict(id="1", league="atp", league_name="ATP", sport="tenis", date="2026-11-02T18:00Z", state=state, status="Set 2", neutral=True, venue="París, Francia",
             home=P("1590", "Carlos Alcaraz", "C. Alcaraz", [6, 3] if state == "in" else [], 1), away=P("3953", "Jannik Sinner", "J. Sinner", [4, 2] if state == "in" else [], 2), note=None)
    d = dict(game=g, kind="tennis", odds=None, gaps=[], form={"home": [], "away": []}, market=None, model=None, picks=None)
    if state == "in": d["live"] = dict(state="in", text="Set 2", clock=None, period=None, situation=None, linescores=None, server=server, stats=[], plays=[])
    return d

def with_pred(d):
    """Agrega una predicción construida con server.prediction.build sobre un modelo sintético (MOCK)."""
    from server import prediction as P, model as M
    d = copy.deepcopy(d); g = d["game"]; odds = dict(total=dict(over=dict(line=2.5)), spread=dict(home=dict(line=-0.5)), book="MOCK")
    if d["kind"] == "tennis":
        d["pred"] = P.build(dict(best_of=3), M.tennis_model(9000, 6000), dict(total=dict(over=dict(line=21.5)), spread=dict(home=dict(line=-2.5)), book="MOCK"), "tennis")
    elif g["sport"] == "futbol":
        lh, la = 1.7, .9; pm = lambda l: M.pois_pmf(l, 12)
        mat = [[pm(lh)[i] * pm(la)[j] for j in range(13)] for i in range(13)]; z = sum(map(sum, mat)); mat = [[x / z for x in r] for r in mat]
        mdl = dict(lam_home=lh, lam_away=la, p_home=.55, p_draw=.25, p_away=.20, total=lambda t: M.cover_matrix(mat, lambda i, j: i + j, t), cover=lambda t: M.cover_matrix(mat, lambda i, j: i - j, t))
        d["pred"] = P.build(g, mdl, None, "soccer", dict(home=5.8, away=4.1, total=9.9, line=9.5, sd=3.4, n=[6, 6]))   # sin mercado -> líneas del modelo; córners MOCK
    else:
        mu, sg, T, ts = 3.0, 13.0, 44.5, 10.0
        mdl = dict(mu=mu, sigma=sg, exp_total=T, tsigma=ts, p_home=.6, p_away=.4, total=lambda t: M.cover_normal(T, ts, t), cover=lambda t: M.cover_normal(mu, sg, t))
        d["pred"] = P.build(g, mdl, dict(total=dict(over=dict(line=43.5)), spread=dict(home=dict(line=-2.5)), book="MOCK"), "football")
    d["pred"].update(locked=False, start_ts=1)
    return d
