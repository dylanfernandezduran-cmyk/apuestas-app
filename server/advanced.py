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

# ---- NFL: EPA/jugada (nflverse)
async def nfl(game):
    R = await ratings.get_ratings("nfl", wait=False)
    E = (R or {}).get("epa")
    if not E: return None
    sides = {}
    for s in ("home", "away"):
        v = E.get(str(((game or {}).get(s) or {}).get("id") or ""))
        if not v: return None
        sides[s] = dict(off=v["off"], deff=v["deff"], net=v["net"], pass_off=v["pass_off"], games=v["games"], plays=v["plays"])
    return dict(cols=[("off", "EPA/jug of."), ("deff", "EPA/jug perm."), ("net", "EPA neta"), ("pass_off", "EPA/pase"), ("games", "JJ")],
                sides=sides, src="nflverse (play-by-play)", src_url="https://github.com/nflverse/nflverse-data/releases/tag/pbp",
                note="Temporada regular actual, pases + carreras. Defensa: EPA permitida (menos es mejor). La EPA neta entra al modelo de margen (backtest: mejora Brier y log loss fuera de muestra en 2025 y 2026).")

# ---- MLB: Baseball Savant (xERA del abridor, xwOBA del equipo)
SAV_P = "https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=pitcher&year={y}&position=&team=&min=1&csv=true"
SAV_T = "https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=batter-team&year={y}&position=&team=&min=q&csv=true"
_SAV = {}

def _norm(x):
    import unicodedata
    x = unicodedata.normalize("NFKD", x or "").encode("ascii", "ignore").decode().lower()
    return " ".join(x.replace(".", " ").replace("-", " ").split())

def parse_csv(txt):
    import csv, io
    return list(csv.DictReader(io.StringIO(txt.lstrip("\ufeff"))))

async def _savant(kind, year):
    from .cache import fetch_bytes
    k = (kind, year); c = _SAV.get(k)
    import time as _t
    if c and _t.time() - c[0] < 6 * 3600: return c[1]
    res = await fetch_bytes((SAV_P if kind == "p" else SAV_T).format(y=year), headers={"User-Agent": "Mozilla/5.0"})
    rows = parse_csv(res[0].decode("utf-8", "replace")) if res else []
    _SAV[k] = (_t.time(), rows); return rows

def _f(x):
    try: return float(x)
    except Exception: return None

async def mlb(r):
    from datetime import datetime
    g = r.get("game") or {}
    try: year = int((g.get("date") or "")[:4]) or datetime.now().year
    except Exception: year = datetime.now().year
    pit, tea = await _savant("p", year), await _savant("t", year)
    if not pit and not tea: return None
    P = r.get("pitchers") or {}
    sides = {}
    for s in ("home", "away"):
        t = g.get(s) or {}; nick = _norm((t.get("name") or "").split()[-1] if t.get("name") else "")
        tr = next((x for x in tea if _norm(x.get("team")) and _norm(x.get("team")).split()[-1] == nick), None)
        o = dict(xwoba=_f(tr.get("est_woba")) if tr else None, woba=_f(tr.get("woba")) if tr else None, pitcher=None, xera=None, era=None)
        pn = (P.get(s) or {}).get("name")
        if pn:
            o["pitcher"] = pn
            want = _norm(pn)
            for x in pit:
                ln, _, fn = (x.get("last_name, first_name") or "").partition(",")
                if _norm(f"{fn} {ln}") == want:
                    o["xera"], o["era"] = _f(x.get("xera")), _f(x.get("era")); break
        sides[s] = o
    if not any(v["xwoba"] or v["xera"] for v in sides.values()): return None
    return dict(cols=[("xwoba", "xwOBA eq."), ("woba", "wOBA eq."), ("pitcher", "Abridor"), ("xera", "xERA"), ("era", "ERA")], sides=sides,
                src="Baseball Savant", src_url="https://baseballsavant.mlb.com/leaderboard/expected_statistics",
                note=f"Temporada {year} · Statcast. Sólo informativo (no entra al modelo: no hay backtest con datos al momento de cada juego). wRC+ (FanGraphs) no disponible: la fuente bloquea el acceso.")

async def attach(r, league):
    try:
        if r.get("advanced"): return
        a = None
        if league == "nba": a = await nba(r.get("game"))
        elif league == "nfl": a = await nfl(r.get("game"))
        elif league == "mlb": a = await mlb(r)
        elif (r.get("game") or {}).get("sport") == "futbol":
            from . import xg as XG
            a = await XG.soccer(r, league)
        if a: r["advanced"] = a
    except Exception:
        pass
