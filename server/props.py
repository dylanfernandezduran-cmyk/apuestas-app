"""Props de jugadores (pt84u): líneas y cuotas REALES de DraftKings vía ESPN core API (propBets) + bitácora de juegos REAL de ESPN (athlete gamelog).
Nada se inventa: si un jugador no tiene línea publicada se muestra «Sin línea» y la tendencia se calcula contra una REFERENCIA (promedio de sus últimos 10 juegos
llevado a x.5) claramente marcada como tal. Los tipos de prop disponibles dependen de lo que DraftKings publique para cada juego (varía por deporte y por día)."""
import asyncio, math, re, time
from datetime import datetime, timezone
from .cache import get_json, _curl_get, _store as _CACHE, _key as _CKEY
from .config import ESPN, LEAGUES

CORE = "https://sports.core.api.espn.com/v2/sports"
WEB = "https://site.web.api.espn.com/apis/common/v3/sports"

# ----------------------------------------------------------------- definición de estadísticas por familia: (etiqueta ES, nombres de columnas de la bitácora ESPN a sumar)
def _outs(g):
    v = g("innings")
    if v is None: return None
    ip = float(v); whole = math.floor(ip + 1e-9); frac = round((ip - whole) * 10)
    return whole * 3 + frac
def _tb(g):
    h, d, t, hr = g("hits"), g("doubles"), g("triples"), g("homeRuns")
    return None if None in (h, d, t, hr) else h + d + 2 * t + 3 * hr
def _singles(g):
    h, d, t, hr = g("hits"), g("doubles"), g("triples"), g("homeRuns")
    return None if None in (h, d, t, hr) else h - d - t - hr

STATS = {
    "basketball": {
        "pts": ("Puntos", ["points"]), "reb": ("Rebotes", ["totalRebounds"]), "ast": ("Asistencias", ["assists"]),
        "fg3": ("Triples", ["threePointFieldGoalsMade-threePointFieldGoalsAttempted"]), "stl": ("Robos", ["steals"]), "blk": ("Bloqueos", ["blocks"]),
        "pr": ("Pts + Reb", ["points", "totalRebounds"]), "pa": ("Pts + Ast", ["points", "assists"]), "ar": ("Ast + Reb", ["assists", "totalRebounds"]),
        "pra": ("Pts + Reb + Ast", ["points", "totalRebounds", "assists"]), "sb": ("Robos + Bloqueos", ["steals", "blocks"]),
    },
    "football": {
        "pass_yds": ("Yardas de pase", ["passingYards"]), "pass_cmp": ("Pases completos", ["completions"]), "pass_att": ("Pases intentados", ["passingAttempts"]),
        "pass_td": ("TD de pase", ["passingTouchdowns"]), "int": ("Intercepciones", ["interceptions"]),
        "rush_yds": ("Yardas por tierra", ["rushingYards"]), "rush_att": ("Acarreos", ["rushingAttempts"]),
        "rec_yds": ("Yardas por recepción", ["receivingYards"]), "rec": ("Recepciones", ["receptions"]),
        "rush_rec_yds": ("Yardas tierra + recepción", ["rushingYards", "receivingYards"]), "pass_rush_yds": ("Yardas pase + tierra", ["passingYards", "rushingYards"]),
        "td": ("TD (cualquier momento)", ["rushingTouchdowns", "receivingTouchdowns"]), "td2": ("2+ TD", ["rushingTouchdowns", "receivingTouchdowns"]),
    },
    "hockey": {
        "goals": ("Gol (cualquier momento)", ["goals"]), "goals2": ("2+ goles", ["goals"]), "goals3": ("3+ goles", ["goals"]), "ast": ("Asistencias", ["assists"]),
        "pts": ("Puntos", ["points"]), "shots": ("Tiros a gol", ["shotsTotal"]),
    },
    "baseball": {
        "hits": ("Hits", ["hits"]), "tb": ("Bases totales", _tb), "runs": ("Carreras", ["runs"]), "rbi": ("Carreras impulsadas", ["RBIs"]),
        "hrr": ("Hits + Carreras + CI", ["hits", "runs", "RBIs"]), "singles": ("Sencillos", _singles), "doubles": ("Dobles", ["doubles"]), "hr": ("Jonrones", ["homeRuns"]),
        "sb": ("Bases robadas", ["stolenBases"]),
        "p_k": ("Ponches (lanzador)", ["strikeouts"]), "p_h": ("Hits permitidos", ["hits"]), "p_er": ("Carreras limpias permitidas", ["earnedRuns"]),
        "p_bb": ("Bases por bolas permitidas", ["walks"]), "p_outs": ("Outs registrados", _outs),
    },
    "soccer": {
        "shots": ("Tiros", ["totalShots"]), "sot": ("Tiros a puerta", ["shotsOnTarget"]), "ast": ("Asistencias", ["goalAssists"]),
        "goals": ("Gol (cualquier momento)", ["totalGoals"]), "goals2": ("2+ goles", ["totalGoals"]), "goals3": ("3+ goles", ["totalGoals"]),
        "cards": ("Tarjeta", ["yellowCards", "redCards"]),
    },
}

# nombre de tipo de prop de ESPN/DraftKings (normalizado) -> (clave, clase, línea fija)   clase: ou = más/menos con 2 precios · ms = «N+» (sólo Más) · yes = sí/no (sólo Sí)
_BB = {"points": "pts", "rebounds": "reb", "assists": "ast", "3-point field goals": "fg3", "steals": "stl", "blocks": "blk", "points and rebounds": "pr", "points and assists": "pa",
       "assists and rebounds": "ar", "points, rebounds, and assists": "pra", "steals and blocks": "sb"}
_BBM = {"points": "pts", "rebounds": "reb", "assists": "ast", "3-point field goals": "fg3", "steals": "stl", "blocks": "blk", "points + rebounds": "pr", "points + assists": "pa",
        "assists + rebounds": "ar", "points + assists + rebounds": "pra", "points + rebounds + assists": "pra", "steals + blocks": "sb"}
TYPES = {
    "basketball": {**{f"total {k}": (v, "ou", None) for k, v in _BB.items()}, **{f"{k} milestones": (v, "ms", None) for k, v in _BBM.items()}},
    "football": {
        "total passing yards": ("pass_yds", "ou", None), "total pass completions": ("pass_cmp", "ou", None), "total passing attempts": ("pass_att", "ou", None),
        "total passing touchdowns": ("pass_td", "ou", None), "total passing interceptions": ("int", "ou", None), "total rushing yards": ("rush_yds", "ou", None),
        "total carries": ("rush_att", "ou", None), "total receiving yards": ("rec_yds", "ou", None), "total receptions": ("rec", "ou", None),
        "total rushing plus receiving yards": ("rush_rec_yds", "ou", None), "total passing plus rushing yards": ("pass_rush_yds", "ou", None),
        "passing yards milestones": ("pass_yds", "ms", None), "rushing yards milestones": ("rush_yds", "ms", None), "receiving yards milestones": ("rec_yds", "ms", None),
        "receptions milestones": ("rec", "ms", None), "anytime touchdown scorer": ("td", "yes", .5), "player to score 2 or more touchdowns": ("td2", "yes", 1.5),
    },
    "hockey": {
        "anytime goalscorer": ("goals", "yes", .5), "to score 2+ goals": ("goals2", "yes", 1.5), "to score 3+ goals": ("goals3", "yes", 2.5),
        "assists milestones": ("ast", "ms", None), "points milestones": ("pts", "ms", None), "shots milestones": ("shots", "ms", None),
        "total shots on goal": ("shots", "ou", None), "total points": ("pts", "ou", None), "total assists": ("ast", "ou", None),
    },
    "baseball": {
        "total hits": ("hits", "ou", None), "total bases": ("tb", "ou", None), "total runs scored": ("runs", "ou", None), "total rbis": ("rbi", "ou", None),
        "total hits + runs + rbis": ("hrr", "ou", None), "total singles hit": ("singles", "ou", None), "total doubles hit": ("doubles", "ou", None), "total stolen bases": ("sb", "ou", None),
        "total strikeouts": ("p_k", "ou", None), "total hits allowed": ("p_h", "ou", None), "earned runs allowed": ("p_er", "ou", None), "total walks allowed": ("p_bb", "ou", None),
        "total outs recorded": ("p_outs", "ou", None),
        "hits milestones": ("hits", "ms", None), "total bases milestones": ("tb", "ms", None), "rbis milestones": ("rbi", "ms", None), "home runs milestones": ("hr", "ms", None),
        "singles milestones": ("singles", "ms", None), "strikeouts thrown milestones": ("p_k", "ms", None), "hits allowed milestones": ("p_h", "ms", None), "walks allowed milestones": ("p_bb", "ms", None),
    },
    "soccer": {
        "shots milestones": ("shots", "ms", None), "shots on target milestones": ("sot", "ms", None), "assists milestones": ("ast", "ms", None),
        "anytime goalscorer": ("goals", "yes", .5), "to score 2+ goals": ("goals2", "yes", 1.5), "to score 3+ goals": ("goals3", "yes", 2.5), "to receive a card": ("cards", "yes", .5),
        "total shots": ("shots", "ou", None), "total shots on target": ("sot", "ou", None),
    },
}
# estadística principal para ordenar jugadores en la lista
MAIN = {"basketball": ["pts", "reb", "ast"], "football": ["pass_yds", "rush_yds", "rec_yds", "rec"], "hockey": ["goals", "shots", "pts"], "baseball": ["hits", "p_k", "tb"], "soccer": ["shots", "goals", "sot"]}
# categoría de «líderes» de ESPN -> clave (para el modo referencia cuando no hay líneas publicadas)
LEADER_CAT = {
    "basketball": {"Points": "pts", "Rebounds": "reb", "Assists": "ast"},
    "football": {"Passing Yards": "pass_yds", "Rushing Yards": "rush_yds", "Receiving Yards": "rec_yds"},
    "hockey": {"Goals": "goals", "Assists": "ast", "Points": "pts"},
    "baseball": {"Hits": "hits", "Strikeouts": "p_k"},
    "soccer": {"Total Shots": "shots", "Assists": "ast"},
}
# bitácora: temporada actual + anterior (año de temporada ESPN) para completar 20 juegos
def _season_year(family, now=None):
    n = now or datetime.now(timezone.utc)
    if family in ("basketball", "hockey"): return n.year + (1 if n.month >= 8 else 0)
    if family == "football": return n.year if n.month >= 3 else n.year - 1
    if family == "baseball": return n.year
    return None

def norm_type(name):
    return re.sub(r"\s+", " ", re.sub(r"\(incl\. overtime\)", "", (name or "").lower())).strip()

def _f(x):
    try:
        v = float(str(x).replace("+", "").strip()); return v
    except Exception: return None

def _price(x):
    """'+105' / '-110' / 105 -> int americano, o None."""
    try:
        v = int(float(str(x).replace("+", "").strip())); return v if v and abs(v) >= 100 else None
    except Exception: return None

def _aid(it):
    m = re.search(r"/athletes/(\d+)", ((it.get("athlete") or {}).get("$ref") or ""))
    return m.group(1) if m else None

def imp(american):
    if american is None: return None
    return 100 / (american + 100) if american > 0 else -american / (-american + 100)

def parse_items(items, family):
    """Items de propBets de ESPN -> {(athlete_id, clave): prop}. over/under por ORDEN dentro del par (el 1º es el Más): verificado contra los «N+» (misma cuota que Más N-0.5).
    Sólo tipos conocidos; sin línea numérica no se incluye. -> prop = dict(aid,key,kind,line,open,over,under,updated,type)"""
    types = TYPES.get(family, {})
    groups = {}
    for it in items:
        aid = _aid(it)
        if not aid: continue
        t = norm_type((it.get("type") or {}).get("name"))
        if t not in types or "1st" in t or "quarter" in t or "half" in t: continue
        key, kind, fixed = types[t]
        cur, opn = it.get("current") or {}, it.get("open") or {}
        tg = ((cur.get("target") or {}).get("value"))
        line = _f(tg) if tg is not None else fixed
        if kind == "ms" and line is not None: line = line - .5             # «N+» = Más de N-0.5
        if kind == "yes": line = fixed
        if line is None: continue
        ot = (opn.get("target") or {}).get("value")
        oline = (_f(ot) - (.5 if kind == "ms" else 0)) if ot is not None and _f(ot) is not None else line
        od = it.get("odds") or {}
        pa = _price(((od.get("american") or {}).get("value")))
        ov = _price(((cur.get("over") or {}).get("american"))); un = _price(((cur.get("under") or {}).get("american")))
        groups.setdefault((aid, key, kind, line), []).append(dict(price=pa, over=ov, under=un, open=oline, updated=it.get("lastUpdated"), type=(it.get("type") or {}).get("name")))
    out = {}
    for (aid, key, kind, line), rows in groups.items():
        r0 = rows[0]
        if kind == "ou":
            over = r0["over"] if r0["over"] is not None else r0["price"]
            under = r0["under"] if r0["under"] is not None else (rows[1]["price"] if len(rows) > 1 else None)
            if r0["over"] is None and len(rows) < 2: over, under = r0["price"], None       # un solo precio sin par: no se sabe de qué lado es
            if r0["over"] is None and len(rows) < 2: over = None
        else:
            over = r0["over"] if r0["over"] is not None else r0["price"]; under = None
        p = dict(aid=aid, key=key, kind=kind, line=line, open=r0["open"], over=over, under=under, updated=r0["updated"], type=r0["type"])
        cur = out.get((aid, key))
        if cur is None: out[(aid, key)] = p; continue
        # varias líneas del mismo jugador/estadística: «ou» gana a «N+»; si no, la más cercana a 50% de probabilidad
        score = lambda q: (0 if q["kind"] == "ou" else 1, abs((imp(q["over"]) or .5) - .5))
        if score(p) < score(cur): out[(aid, key)] = p
    return out

def parse_btts(items):
    """«Both Teams To Score» (DraftKings vía ESPN, sin atleta): par de filas, la 1ª = Sí y la 2ª = No (mismo orden que Más/Menos). -> dict(yes,no,open_yes,open_no,updated) o None."""
    rows = [it for it in items if not it.get("athlete") and norm_type((it.get("type") or {}).get("name")) == "both teams to score"]
    if len(rows) != 2: return None
    pr = lambda it, k: _price(((it.get(k) or {}).get("over") or {}).get("american"))
    y, n = rows
    if pr(y, "current") is None or pr(n, "current") is None: return None
    return dict(yes=pr(y, "current"), no=pr(n, "current"), open_yes=pr(y, "open"), open_no=pr(n, "open"), updated=y.get("lastUpdated"), book="DraftKings")

async def btts_odds(league, eid):
    """Cuotas reales de «Ambos anotan» (DraftKings vía ESPN) o None."""
    if LEAGUES.get(league, {}).get("family") != "soccer": return None
    try: return (await event_props(league, eid)).get(("", "btts"))
    except Exception: return None

# ----------------------------------------------------------------- fuentes
_EVIDX = {}          # (league, eid) -> (ts, {(aid,key): prop})   índice COMPACTO (no se guarda el JSON de 300 KB)
_EVLOCK = {}

async def event_props(league, eid, ttl=300):
    """Props publicados por DraftKings para un evento (todas las páginas) -> {(aid,key): prop} (puede ser {} si aún no hay)."""
    fam = LEAGUES[league]["family"]; path = LEAGUES[league]["path"]
    ent = _EVIDX.get((league, eid))
    if ent and time.time() - ent[0] < ttl: return ent[1]
    lock = _EVLOCK.setdefault((league, eid), asyncio.Lock())
    async with lock:
        ent = _EVIDX.get((league, eid))
        if ent and time.time() - ent[0] < ttl: return ent[1]
        base = f"{CORE}/{path.split("/")[0]}/leagues/{path.split("/")[1]}/events/{eid}/competitions/{eid}/odds/100/propBets"
        items, page, ok = [], 1, False
        while page <= 6:
            params = {"limit": 400, "page": page}
            d = None
            for att in range(3):                               # ESPN a veces responde 404/5xx transitorio: reintentar y, al final, curl
                d = await get_json(base, ttl=1, params=params)
                _CACHE.pop(_CKEY(base, params), None)          # no retener el JSON crudo
                if d and "items" in d: break
                if att == 1:
                    d = await _curl_get(base, params); 
                    if d and "items" in d: break
                await asyncio.sleep(0.3)
            if not d or "items" not in d: break
            ok = True; items += d["items"]
            if page >= (d.get("pageCount") or 1): break
            page += 1
        idx = parse_items(items, fam) if ok else {}
        if ok and fam == "soccer":
            bt = parse_btts(items)
            if bt: idx[("", "btts")] = bt
        if len(_EVIDX) > 400:
            for k in sorted(_EVIDX, key=lambda k: _EVIDX[k][0])[:100]: _EVIDX.pop(k, None)
        _EVIDX[(league, eid)] = (time.time() if ok else time.time() - ttl + 20, idx)   # un fallo se reintenta a los 20 s
        return idx

async def athlete_info(league, aid):
    path = LEAGUES[league]["path"]
    d = await get_json(f"{WEB}/{path}/athletes/{aid}", ttl=43200)
    a = (d or {}).get("athlete") or {}
    if not a: return None
    t = a.get("team") or {}
    hs = (a.get("headshot") or {}).get("href")
    return dict(id=str(aid), name=a.get("displayName") or a.get("fullName"), jersey=a.get("jersey"), pos=(a.get("position") or {}).get("abbreviation"),
                pos_name=(a.get("position") or {}).get("displayName"), img=hs, team=dict(id=str(t.get("id") or ""), abbr=t.get("abbreviation"), name=t.get("displayName"),
                logo=(t.get("logos") or [{}])[0].get("href") if t.get("logos") else None))

def parse_gamelog(d):
    """gamelog de ESPN -> lista de juegos [{eid,date,opp,home,result,score,s:{col:valor}}] (sin pretemporada), más reciente primero."""
    if not d: return []
    names = d.get("names") or []; evs = d.get("events") or {}
    out, seen = [], set()
    for st in d.get("seasonTypes") or []:
        if "preseason" in (st.get("displayName") or "").lower(): continue
        for cat in st.get("categories") or []:
            for e in cat.get("events") or []:
                eid = str(e.get("eventId")); meta = evs.get(eid)
                if not meta or eid in seen: continue
                seen.add(eid)
                s = dict(zip(names, e.get("stats") or []))
                out.append(dict(eid=eid, date=meta.get("gameDate"), opp=(meta.get("opponent") or {}).get("abbreviation"), home=(meta.get("atVs") == "vs"), result=meta.get("gameResult"),
                                score=meta.get("score"), s=s))
    out.sort(key=lambda g: g["date"] or "", reverse=True)
    return out

async def gamelog(league, aid, need=20):
    fam = LEAGUES[league]["family"]; path = LEAGUES[league]["path"]
    base = f"{WEB}/{path}/athletes/{aid}/gamelog"
    cur = parse_gamelog(await get_json(base, ttl=1800))
    y = _season_year(fam)
    if len(cur) < need and y:
        prev = parse_gamelog(await get_json(base, ttl=21600, params={"season": y - 1}))
        have = {g["eid"] for g in cur}
        cur += [g for g in prev if g["eid"] not in have]
        cur.sort(key=lambda g: g["date"] or "", reverse=True)
    return cur

def stat_value(family, key, s):
    """Valor de la estadística `key` en un juego (dict de columnas de ESPN) o None si no hay datos reales de esa columna."""
    spec = STATS[family].get(key)
    if not spec: return None
    def g(name):
        v = s.get(name)
        if v is None or v in ("-", ""): return None
        if isinstance(v, str) and re.fullmatch(r"\d+-\d+", v): return float(v.split("-")[0])        # «7-14» (hechos-intentos): se toma los hechos
        return _f(v)
    cols = spec[1]
    if callable(cols): return cols(g)
    vals = [g(c) for c in cols]
    return None if any(v is None for v in vals) else sum(vals)

def reference_line(vals, n=10):
    """Línea de REFERENCIA (no es de casa de apuestas): promedio de los últimos n juegos llevado a x.5."""
    v = [x for x in vals[:n] if x is not None]
    if len(v) < 3: return None
    m = sum(v) / len(v)
    return dict(line=math.floor(m) + .5, avg=m, n=len(v))

def hit_stats(vals, line, side="over", n=10):
    """-> dict(hit, n, push, pct) sobre los últimos n valores (None se ignora)."""
    v = [x for x in vals[:n] if x is not None]
    hit = sum(1 for x in v if (x > line if side == "over" else x < line)); push = sum(1 for x in v if x == line)
    return dict(hit=hit, n=len(v), push=push, pct=(hit / (len(v) - push) if len(v) - push else None))

# ----------------------------------------------------------------- vistas (lista del juego y detalle de un jugador)
async def _summary(league, eid):
    path = LEAGUES[league]["path"]
    return await get_json(f"{ESPN}/{path}/summary", ttl=300, params={"event": eid})

def _teams(summ):
    out = []
    comp = (((summ or {}).get("header") or {}).get("competitions") or [{}])[0]
    for c in comp.get("competitors") or []:
        t = c.get("team") or {}
        out.append(dict(id=str(t.get("id")), abbr=t.get("abbreviation"), name=t.get("displayName"), home=c.get("homeAway") == "home"))
    return out

def _leaders_ref(summ, fam):
    """Modo referencia: líderes de cada equipo (ESPN) -> [(aid, key)] cuando DraftKings aún no publica props."""
    from .data import _leaders
    lead = _leaders(summ) or {}
    out, seen = [], set()
    cats = LEADER_CAT.get(fam, {})
    for tid, rows in lead.items():
        n = 0
        for r in rows:
            k = cats.get(r.get("cat"))
            if k and r.get("id") and (r["id"], k) not in seen and n < 4:
                seen.add((r["id"], k)); out.append((str(r["id"]), k, str(tid))); n += 1
    return out

async def _mini(league, fam, aid, key, prop, sem):
    async with sem:
        try:
            info, log = await asyncio.gather(athlete_info(league, aid), gamelog(league, aid, need=10))
        except Exception:
            return None
    if not info: return None
    vals = [stat_value(fam, key, g["s"]) for g in log]
    ref = None
    if prop is None: ref = reference_line(vals)
    line = prop["line"] if prop else (ref["line"] if ref else None)
    hs = hit_stats(vals, line, "over", 10) if line is not None else None
    return info, dict(key=key, label=STATS[fam][key][0], line=line, open=(prop or {}).get("open"), over=(prop or {}).get("over"), under=(prop or {}).get("under"), kind=(prop or {}).get("kind", "ou"),
                      ref=prop is None, avg=(sum(x for x in vals[:10] if x is not None) / max(1, len([x for x in vals[:10] if x is not None])) if any(x is not None for x in vals[:10]) else None),
                      l10=hs, last=[x for x in vals[:10]], updated=(prop or {}).get("updated"))

async def game_props(league, eid, maxp=16):
    """Props de jugadores de un juego: {mode, players:[{id,name,jersey,pos,team,img,props:[…]}], stats:[{key,label}], teams, src, note}."""
    fam = LEAGUES[league]["family"]
    if fam == "tennis": return dict(mode="none", players=[], stats=[], note="Tenis: ninguna fuente pública publica props de jugador (aces, juegos) → no se muestran.")
    summ = await _summary(league, eid)
    teams = _teams(summ); tids = {t["id"] for t in teams}
    idx = await event_props(league, eid)
    sem = asyncio.Semaphore(8)
    mode, jobs = "lineas", []
    if any(a for a, _ in idx):
        by = {}
        for (aid, key), p in idx.items():
            if aid: by.setdefault(aid, []).append(p)          # ("", "btts") es de equipo, no de jugador
        # jugadores con más props y línea de su estadística principal más alta primero
        main = MAIN.get(fam, [])
        def rank(aid):
            ps = by[aid]; mp = next((p for k in main for p in ps if p["key"] == k), None)
            return (-len(ps), -(mp["line"] if mp else 0))
        # primero se reúne info de atleta (equipo) para filtrar a los dos equipos del juego
        aids = sorted(by, key=rank)[:maxp + 8]
        infos = await asyncio.gather(*[athlete_info(league, a) for a in aids], return_exceptions=True)
        keep = [a for a, i in zip(aids, infos) if isinstance(i, dict) and i and (not tids or i["team"]["id"] in tids)][:maxp]
        for a in keep:
            ps = sorted(by[a], key=lambda p: (0 if p["kind"] == "ou" else 1, main.index(p["key"]) if p["key"] in main else 9))
            for p in ps[:12]: jobs.append((a, p["key"], p))
    else:
        mode = "referencia"
        for aid, key, tid in _leaders_ref(summ, fam): jobs.append((aid, key, None))
    res = await asyncio.gather(*[_mini(league, fam, a, k, p, sem) for a, k, p in jobs])
    players, order = {}, []
    for r in res:
        if not r: continue
        info, pr = r
        if info["id"] not in players: players[info["id"]] = dict(info, props=[]); order.append(info["id"])
        players[info["id"]]["props"].append(pr)
    plist = [players[a] for a in order]
    stats, seen = [], set()
    for pl in plist:
        for pr in pl["props"]:
            if pr["key"] not in seen: seen.add(pr["key"]); stats.append(dict(key=pr["key"], label=pr["label"]))
    src = "DraftKings (vía ESPN)" if mode == "lineas" else None
    note = None
    if mode == "referencia":
        note = "DraftKings aún no publica props de jugadores para este juego (suelen salir el mismo día). Se muestran los líderes de cada equipo con tendencia contra una REFERENCIA calculada (promedio de sus últimos 10 juegos llevado a x.5), no una línea de casa de apuestas."
    if not plist and mode == "lineas": mode = "none"
    if not plist: note = note or "Sin props disponibles para este juego."
    return dict(mode=mode, players=plist, stats=stats, teams=teams, src=src, note=note, ts=time.time())

async def player_prop(league, eid, aid, key, hist=10):
    """Detalle de un jugador/estadística: info, línea (real o referencia), juegos recientes (valor + línea histórica de mercado si existe), mercados disponibles."""
    fam = LEAGUES[league]["family"]
    if key not in STATS.get(fam, {}): return None
    idx = await event_props(league, eid)
    info, log = await asyncio.gather(athlete_info(league, aid), gamelog(league, aid, need=20))
    if not info: return None
    vals = [stat_value(fam, key, g["s"]) for g in log]
    prop = idx.get((aid, key))
    ref = None if prop else reference_line(vals)
    games = [dict(eid=g["eid"], date=g["date"], opp=g["opp"], home=g["home"], result=g["result"], score=g["score"], value=v) for g, v in zip(log[:20], vals[:20]) if v is not None]
    # línea de mercado de CADA juego pasado (DraftKings conserva los props de eventos terminados); sólo para «más/menos» con 2 precios
    if prop and prop["kind"] == "ou" and hist:
        sem = asyncio.Semaphore(10)
        async def one(g):
            async with sem:
                try: ix = await event_props(league, g["eid"], ttl=86400)
                except Exception: return
            p = ix.get((aid, key))
            if p and p["kind"] == "ou": g["line_hist"] = p["line"]; g["over_hist"] = p["over"]; g["under_hist"] = p["under"]
        await asyncio.gather(*[one(g) for g in games[:hist]])
    mk = []
    for (a, k), p in idx.items():
        if a == aid: mk.append(dict(key=k, label=STATS[fam][k][0], line=p["line"], over=p["over"], under=p["under"], kind=p["kind"]))
    if not mk:
        for k in MAIN.get(fam, []):
            r = reference_line([stat_value(fam, k, g["s"]) for g in log])
            if r: mk.append(dict(key=k, label=STATS[fam][k][0], line=r["line"], ref=True))
    order = {k: i for i, k in enumerate(STATS[fam])}
    mk.sort(key=lambda m: order.get(m["key"], 99))
    line = prop["line"] if prop else (ref["line"] if ref else None)
    return dict(info=info, key=key, label=STATS[fam][key][0], family=fam,
                line=dict(value=line, open=(prop or {}).get("open"), over=(prop or {}).get("over"), under=(prop or {}).get("under"), kind=(prop or {}).get("kind", "ou"),
                          ref=prop is None, ref_avg=(ref or {}).get("avg"), ref_n=(ref or {}).get("n"), updated=(prop or {}).get("updated"), src="DraftKings (vía ESPN)" if prop else None),
                games=games, markets=mk, hist_n=(hist if prop and prop['kind']=='ou' else 0), ts=time.time())
