"""Fútbol: xG / xGA por equipo desde Understat (getLeagueData, público). Sólo informativo.
Si Understat no responde (p. ej. mantenimiento) no se muestra nada: nunca se inventa."""
import time, unicodedata
import httpx

LG = {"eng.1": "EPL", "esp.1": "La_liga", "ita.1": "Serie_A", "ger.1": "Bundesliga", "fra.1": "Ligue_1"}
_C = {}
H = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}

def _n(x):
    x = unicodedata.normalize("NFKD", x or "").encode("ascii", "ignore").decode().lower()
    return " ".join(x.replace(".", " ").replace("-", " ").split())

def season_now(now=None):
    from datetime import datetime
    d = datetime.fromtimestamp(now or time.time()); return d.year if d.month >= 7 else d.year - 1

def table(data):
    out = {}
    teams = (data or {}).get("teams") or {}
    for t in (teams.values() if isinstance(teams, dict) else teams):
        hist = t.get("history") or []
        if not hist: continue
        n = len(hist)
        xg = sum(float(h.get("xG") or 0) for h in hist); xga = sum(float(h.get("xGA") or 0) for h in hist)
        gf = sum(float(h.get("scored") or 0) for h in hist); ga = sum(float(h.get("missed") or 0) for h in hist)
        out[_n(t.get("title"))] = dict(xg=round(xg / n, 2), xga=round(xga / n, 2), gf=round(gf / n, 2), ga=round(ga / n, 2), n=n, title=t.get("title"))
    return out

async def league_table(league):
    slug = LG.get(league)
    if not slug: return None
    c = _C.get(league)
    if c and time.time() - c[0] < 6 * 3600: return c[1]
    y = season_now(); tab = None
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers=H) as cl:
            await cl.get(f"https://understat.com/league/{slug}/{y}")
            r = await cl.get(f"https://understat.com/getLeagueData/{slug}/{y}", headers={"Referer": f"https://understat.com/league/{slug}/{y}"})
            if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                tab = table(r.json())
    except Exception:
        tab = None
    _C[league] = (time.time(), tab)
    return tab

def _find(tab, team):
    nm = _n((team or {}).get("name")); sh = _n((team or {}).get("short") or "")
    if nm in tab: return tab[nm]
    for k, v in tab.items():
        if k and (k in nm or nm in k or (sh and (sh in k or k in sh))): return v
    return None

async def soccer(r, league):
    tab = await league_table(league)
    if not tab: return None
    g = r.get("game") or {}
    sides = {s: _find(tab, g.get(s)) for s in ("home", "away")}
    if not all(sides.values()): return None
    return dict(cols=[("xg", "xG/PJ"), ("xga", "xGA/PJ"), ("gf", "GF/PJ"), ("ga", "GC/PJ"), ("n", "PJ")], sides=sides,
                src="Understat", src_url=f"https://understat.com/league/{LG[league]}", note="Temporada actual · Understat. Sólo informativo (sin backtest todavía).")
