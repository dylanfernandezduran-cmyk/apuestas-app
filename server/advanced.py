"""Estadística avanzada por equipo desde fuentes públicas gratuitas (ESPN team statistics).
NBA: eFG%, TS%, ritmo (posesiones/juego, estimado), ORtg, DRtg y Net (por 100 posesiones).
Fórmulas estándar (Dean Oliver): poss ≈ FGA − OREB + TOV + 0.44·FTA. DRtg usa puntos permitidos
de los últimos N juegos de la temporada (N = juegos jugados según ESPN) y las posesiones propias como
aproximación (ESPN no publica las del rival). Si falta un dato se deja en None: nada inventado."""
from .cache import get_json
from . import ratings

URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{tid}/statistics"
COLS = [("efg", "eFG%"), ("ts", "TS%"), ("pace", "Ritmo"), ("ortg", "ORtg"), ("drtg", "DRtg"), ("net", "Net")]

def _stats(js):
    out = {}
    for c in (((js or {}).get("results") or {}).get("stats") or {}).get("categories") or []:
        for s in c.get("stats") or []:
            if s.get("value") is not None: out[s["name"]] = float(s["value"])
    return out

def compute(st, opp_ppg=None):
    g = lambda k: st.get(k)
    fga, fgm, tpm, fta, pts = g("avgFieldGoalsAttempted"), g("avgFieldGoalsMade"), g("avgThreePointFieldGoalsMade"), g("avgFreeThrowsAttempted"), g("avgPoints")
    orb, tov = g("avgOffensiveRebounds"), g("avgTurnovers")
    o = dict(efg=None, ts=None, pace=None, ortg=None, drtg=None, net=None, gp=g("gamesPlayed"))
    if fga and fgm is not None and tpm is not None: o["efg"] = round(100 * (fgm + 0.5 * tpm) / fga, 1)
    if fga and fta is not None and pts: o["ts"] = round(100 * pts / (2 * (fga + 0.44 * fta)), 1)
    if fga and orb is not None and tov is not None and fta is not None:
        poss = fga - orb + tov + 0.44 * fta
        o["pace"] = round(poss, 1)
        if pts: o["ortg"] = round(100 * pts / poss, 1)
        if opp_ppg: o["drtg"] = round(100 * opp_ppg / poss, 1)
        if o["ortg"] is not None and o["drtg"] is not None: o["net"] = round(o["ortg"] - o["drtg"], 1)
    return o

def _opp_ppg(R, tid, n):
    if not R or not n: return None
    gl = sorted(R.get("team_games", {}).get(tid, []), key=lambda x: x.get("date") or "")[-int(n):]
    if not gl: return None
    return sum((g["as_"] if g["home"] == tid else g["hs"]) for g in gl) / len(gl)

async def nba(game):
    R = await ratings.get_ratings("nba", wait=False)
    sides = {}
    for s in ("home", "away"):
        tid = str(((game or {}).get(s) or {}).get("id") or "")
        if not tid: return None
        try: st = _stats(await get_json(URL.format(tid=tid), ttl=6 * 3600))
        except Exception: st = {}
        if not st: return None
        sides[s] = compute(st, _opp_ppg(R, tid, st.get("gamesPlayed")))
    return dict(cols=COLS, sides=sides, src="ESPN (estadísticas de equipo)",
                note="Temporada actual · ESPN. Ritmo = posesiones estimadas por juego; ORtg/DRtg por 100 posesiones (DRtg aproximado con posesiones propias). Sólo informativo: el backtest no mejoró al sumar net rating al modelo.")

async def attach(r, league):
    try:
        if league == "nba" and not r.get("advanced"):
            a = await nba(r.get("game"))
            if a: r["advanced"] = a
    except Exception:
        pass
