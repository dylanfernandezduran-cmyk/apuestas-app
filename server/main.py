import asyncio, os, time
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import data, ratings, market as MK, history
from .config import SPORTS, LEAGUES
from .cache import STATS

app = FastAPI(title="Apuestas · terminal de picks")
STATIC = os.path.join(os.path.dirname(__file__), "..", "static")

@app.on_event("startup")
async def warm():
    async def w():
        for l in ("nba", "nhl", "nfl", "mex.1", "eng.1", "esp.1", "ita.1", "ger.1", "uefa.champions", "mlb"):
            try: await ratings.get_ratings(l)
            except Exception: pass
    asyncio.create_task(w())
    asyncio.create_task(snapshot_loop())

SNAP_MIN = float(os.environ.get("SNAP_MIN", "10"))   # minutos entre snapshots de líneas
SNAP_STATE = {"last": None, "games": 0, "runs": 0, "err": None}

async def snapshot_once():
    now = datetime.now(timezone.utc); lim = now + timedelta(hours=72)
    leagues = list(LEAGUES.keys())
    lists = await asyncio.gather(*[data.list_games(l) for l in leagues], return_exceptions=True)
    todo = []
    for l, r in zip(leagues, lists):
        if isinstance(r, Exception): continue
        for g in r[0]:
            d = data.parse_dt(g["date"])
            if g["state"] == "pre" and d and now <= d <= lim: todo.append((l, g))
    sem = asyncio.Semaphore(6)
    async def one(l, g):
        async with sem:
            try: await MK.game_market(l, g, snapshot=True)
            except Exception: pass
    await asyncio.gather(*[one(l, g) for l, g in todo])
    SNAP_STATE.update(last=time.time(), games=len(todo), runs=SNAP_STATE["runs"] + 1)

async def snapshot_loop():
    await asyncio.sleep(5)
    while True:
        try: await snapshot_once()
        except Exception as ex: SNAP_STATE["err"] = str(ex)[:200]
        await asyncio.sleep(max(60, SNAP_MIN * 60))

@app.get("/api/sports")
async def sports():
    return [dict(s, leagues=[dict(key=k, name=LEAGUES[k]["name"]) for k in s["leagues"]]) for s in SPORTS]

@app.get("/api/games")
async def games(league: str, days: int | None = None):
    if league not in LEAGUES: raise HTTPException(404, "Liga no soportada")
    gs, ok = await data.list_games(league, days)
    return dict(league=league, name=LEAGUES[league]["name"], ok=ok, games=gs, now=time.time())

_brief_cache = {}

@app.get("/api/league_brief")
async def league_brief(league: str, hours: int = 96):
    """Probabilidades compactas (mejor resultado por mercado) de los juegos próximos de una liga. Para tarjetas de lista."""
    if league not in LEAGUES: raise HTTPException(404, "Liga no soportada")
    ent = _brief_cache.get(league)
    if ent and time.time() - ent[0] < 120: return ent[1]
    gs, ok = await data.list_games(league)
    lim = time.time() + hours * 3600
    gs = [g for g in gs if g["state"] == "pre"][:40]
    sem = asyncio.Semaphore(6)
    async def one(g):
        async with sem:
            try:
                a = await data.analyze(league, g["id"])
            except Exception:
                return g["id"], None
        return g["id"], (data.PR.brief(a.get("probs")) if a and a.get("probs") else [])
    res = dict(league=league, items=dict(await asyncio.gather(*[one(g) for g in gs])), now=time.time())
    _brief_cache[league] = (time.time(), res)
    return res

@app.get("/api/game/{league}/{eid}")
async def game(league: str, eid: str):
    if league not in LEAGUES: raise HTTPException(404, "Liga no soportada")
    r = await data.analyze(league, eid)
    if not r: raise HTTPException(404, "Juego no encontrado o sin datos")
    return r

@app.get("/api/picks")
async def picks(scope: str = "24h"):
    return await data.picks(scope)

@app.get("/api/history/{league}/{eid}")
async def hist(league: str, eid: str):
    return history.series(league, eid)

@app.post("/api/snapshot")
async def snap_now():
    await snapshot_once()
    return dict(SNAP_STATE, db=history.stats())

@app.get("/api/health")
async def health():
    return dict(ok=True, cache=STATS, ratings={k: v["n_games"] for k, v in ratings._ratings.items()}, ts=time.time(), snapshots=dict(SNAP_STATE, every_min=SNAP_MIN, db=history.stats()))

app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC, "index.html"), headers={"Cache-Control": "no-cache"})
