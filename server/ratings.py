"""Construye ratings por liga a partir de los calendarios/resultados REALES de ESPN (todos los equipos)."""
import asyncio, math, time
from collections import defaultdict
from .cache import get_json
from .config import ESPN, LEAGUES, FAMILY, SOCCER

_ratings: dict = {}
_building: dict = {}

def _score(c):
    s = c.get("score")
    if isinstance(s, dict): s = s.get("value", s.get("displayValue"))
    try: return float(s)
    except Exception: return None

async def _team_ids(path):
    d = await get_json(f"{ESPN}/{path}/teams", ttl=86400, params={"limit": 200})
    try:
        return [(t["team"]["id"], t["team"]["displayName"]) for t in d["sports"][0]["leagues"][0]["teams"]]
    except Exception:
        return []

def _parse_events(events, games, family):
    for e in events or []:
        try:
            comp = e["competitions"][0]
            if not comp["status"]["type"].get("completed"): continue
            st = (e.get("seasonType") or {}).get("type")
            if family != "soccer" and st == 1: continue   # sin pretemporada
            home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
            away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
            hs, as_ = _score(home), _score(away)
            if hs is None or as_ is None: continue
            games[e["id"]] = dict(id=e["id"], date=e["date"], home=home["team"]["id"], away=away["team"]["id"],
                                  hs=hs, as_=as_, neutral=bool(comp.get("neutralSite")),
                                  hname=home["team"].get("displayName"), aname=away["team"].get("displayName"))
        except Exception:
            continue

async def build(league: str):
    cfg = LEAGUES[league]; fam = cfg["family"]
    teams = await _team_ids(cfg["path"])
    games: dict = {}
    names = dict(teams)
    async def one(tid):
        if fam == "soccer":
            d = await get_json(f"{ESPN}/{cfg['path']}/teams/{tid}/schedule", ttl=3600)
            if d: _parse_events(d.get("events"), games, fam)
        else:  # temporada regular (2) + postemporada (3); sin pretemporada
            for stype in (2, 3):
                d = await get_json(f"{ESPN}/{cfg['path']}/teams/{tid}/schedule", ttl=3600, params={"seasontype": stype})
                if d: _parse_events(d.get("events"), games, fam)
    await asyncio.gather(*[one(t) for t, _ in teams])
    gl = sorted(games.values(), key=lambda g: g["date"])
    R = {"league": league, "family": fam, "n_games": len(gl), "built": time.time(), "names": names,
         "games": gl, "team_games": defaultdict(list)}
    for g in gl:
        R["team_games"][g["home"]].append(g); R["team_games"][g["away"]].append(g)
    if fam == "soccer": _soccer(R)
    else: _margin(R)
    _ratings[league] = R
    return R

def _margin(R):
    fam = FAMILY[R["family"]]; gl = R["games"]
    N = len(gl)
    # HFA liga (con prior)
    hm = sum((g["hs"] - g["as_"]) for g in gl if not g["neutral"]); nn = sum(1 for g in gl if not g["neutral"])
    W = fam["hfa_w"] / 4   # el prior pesa W juegos
    hfa = (hm + W * fam["hfa"]) / (nn + W)
    R["hfa"] = hfa; R["hfa_raw"] = hm / nn if nn else None
    tg = defaultdict(list)
    for g in gl:
        tg[g["home"]].append(g); tg[g["away"]].append(g)
    allpts = [g["hs"] for g in gl] + [g["as_"] for g in gl]
    lg = sum(allpts) / len(allpts) if allpts else None
    R["lg_pts"] = lg
    # SRS iterativo
    r = defaultdict(float)
    for _ in range(40):
        nr = {}
        for t, lst in tg.items():
            tot = 0.0
            for g in lst:
                if g["home"] == t:
                    m = g["hs"] - g["as_"] - (0 if g["neutral"] else hfa); opp = g["away"]
                else:
                    m = g["as_"] - g["hs"] + (0 if g["neutral"] else hfa); opp = g["home"]
                tot += m + r[opp]
            nr[t] = tot / len(lst)
        mean = sum(nr.values()) / len(nr) if nr else 0
        r = defaultdict(float, {t: v - mean for t, v in nr.items()})
    R["srs"] = {t: v for t, v in r.items()}
    R["rating"] = {t: v * len(tg[t]) / (len(tg[t]) + fam["k"]) for t, v in r.items()}
    R["n"] = {t: len(tg[t]) for t in tg}
    # ofensiva/defensa suavizadas (para totales)
    k = fam["k"]; off = {}; dfn = {}
    for t, lst in tg.items():
        pf = sum(g["hs"] if g["home"] == t else g["as_"] for g in lst)
        pa = sum(g["as_"] if g["home"] == t else g["hs"] for g in lst)
        n = len(lst)
        off[t] = (pf + k * lg) / (n + k); dfn[t] = (pa + k * lg) / (n + k)
    R["off"], R["def"] = off, dfn

def _soccer(R):
    gl = R["games"]; S = SOCCER
    N = len(gl)
    H = sum(g["hs"] for g in gl); A = sum(g["as_"] for g in gl)
    R["lg_home"] = (H + S["prior_w"] * S["home_prior"]) / (N + S["prior_w"])
    R["lg_away"] = (A + S["prior_w"] * S["away_prior"]) / (N + S["prior_w"])
    lg_avg = (R["lg_home"] + R["lg_away"]) / 2
    R["lg_avg"] = lg_avg
    tg = defaultdict(list)
    for g in gl:
        tg[g["home"]].append(g); tg[g["away"]].append(g)
    k = S["k"]; att = {}; dfn = {}
    for t, lst in tg.items():
        gf = sum(g["hs"] if g["home"] == t else g["as_"] for g in lst)
        ga = sum(g["as_"] if g["home"] == t else g["hs"] for g in lst)
        n = len(lst)
        att[t] = ((gf + k * lg_avg) / (n + k)) / lg_avg
        dfn[t] = ((ga + k * lg_avg) / (n + k)) / lg_avg
    R["att"], R["def"] = att, dfn
    R["n"] = {t: len(tg[t]) for t in tg}

async def get_ratings(league: str, wait=True):
    R = _ratings.get(league)
    if R and time.time() - R["built"] < 3600: return R
    if league in _building:
        return await _building[league] if wait else R
    async def _b():
        try: return await build(league)
        finally: _building.pop(league, None)
    t = asyncio.ensure_future(_b()); _building[league] = t
    return await t

def team_summary(R, tid, limit=10):
    """Registro, últimos 5/10, splits local/visita calculados con resultados reales."""
    lst = R["team_games"].get(tid, [])
    rows = []
    for g in lst:
        home = g["home"] == tid
        pf = g["hs"] if home else g["as_"]; pa = g["as_"] if home else g["hs"]
        res = "W" if pf > pa else ("L" if pf < pa else "D")
        rows.append(dict(id=g["id"], date=g["date"], home=home, neutral=g["neutral"], pf=pf, pa=pa, res=res,
                         opp=(g["aname"] if home else g["hname"]), opp_id=(g["away"] if home else g["home"])))
    rows.sort(key=lambda x: x["date"])
    def rec(rs):
        w = sum(1 for r in rs if r["res"] == "W"); l = sum(1 for r in rs if r["res"] == "L"); d = sum(1 for r in rs if r["res"] == "D")
        n = len(rs)
        return dict(w=w, l=l, d=d, n=n, pf=(sum(r["pf"] for r in rs) / n if n else None), pa=(sum(r["pa"] for r in rs) / n if n else None),
                    text=(f"{w}-{l}-{d}" if (d or R["family"] == "soccer") else f"{w}-{l}"))
    streak = None
    if rows:
        last = rows[-1]["res"]; c = 0
        for r in reversed(rows):
            if r["res"] == last: c += 1
            else: break
        streak = f"{last}{c}"
    return dict(overall=rec(rows), home=rec([r for r in rows if r["home"] and not r["neutral"]]),
                away=rec([r for r in rows if not r["home"] and not r["neutral"]]),
                last5=rec(rows[-5:]), last10=rec(rows[-10:]), streak=streak,
                form=[r["res"] for r in rows[-10:]], recent=list(reversed(rows[-limit:])), n=len(rows))
