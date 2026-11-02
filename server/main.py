import asyncio, os, time
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import data, ratings, market as MK, history, record as REC, grading
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
    asyncio.create_task(grade_loop())

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
            try: await data.analyze(l, g["id"])    # registra pick principal + sugerencias (aunque nadie abra el juego)
            except Exception: pass
    await asyncio.gather(*[one(l, g) for l, g in todo])
    SNAP_STATE.update(last=time.time(), games=len(todo), runs=SNAP_STATE["runs"] + 1)

async def snapshot_loop():
    await asyncio.sleep(5)
    while True:
        try: await snapshot_once()
        except Exception as ex: SNAP_STATE["err"] = str(ex)[:200]
        await asyncio.sleep(max(60, SNAP_MIN * 60))

GRADE_MIN = float(os.environ.get("GRADE_MIN", "10"))   # minutos entre calificaciones automáticas
GRADE_STATE = {"last": None, "runs": 0, "graded": 0, "err": None, "last_result": None}

async def grade_once():
    r = await grading.grade_pending()
    GRADE_STATE.update(last=time.time(), runs=GRADE_STATE["runs"] + 1, graded=GRADE_STATE["graded"] + r["graded"] + r["void"], last_result=r, err=None)
    return r

async def grade_loop():
    await asyncio.sleep(20)
    while True:
        try: await grade_once()
        except Exception as ex: GRADE_STATE["err"] = str(ex)[:200]
        await asyncio.sleep(max(60, GRADE_MIN * 60))

@app.get("/api/sports")
async def sports():
    return [dict(s, leagues=[dict(key=k, name=LEAGUES[k]["name"]) for k in s["leagues"]]) for s in SPORTS]

@app.get("/api/games")
async def games(league: str, days: int | None = None):
    if league not in LEAGUES: raise HTTPException(404, "Liga no soportada")
    gs, ok = await data.list_games(league, days)
    try:
        rr = REC.games_rows(league, [g["id"] for g in gs])
        for g in gs: g["rec"] = [dict(market=r["market"], selection=r["selection"], type=r["type"], status=r["status"], label=r["label"]) for r in rr.get(g["id"], [])]
    except Exception: pass
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

@app.get("/api/record")
async def record(sport: str | None = None, type: str | None = None, days: int | None = None, limit: int = 60, basis: str | None = None):
    """Récord de picks: resumen (G-P-E, %, unidades a 1u plano con la cuota registrada) + últimos calificados. Filtros: sport, type=main|suggestion, days."""
    return dict(summary=REC.summary(sport, type, days, basis), recent=REC.query(sport, type, days, min(max(limit, 1), 300), basis=basis), grading=dict(GRADE_STATE, every_min=GRADE_MIN),
                filters=dict(sport=sport, type=type, days=days, basis=basis), now=time.time())

@app.post("/api/grade")
async def grade_now():
    """Califica ahora lo pendiente (también corre solo cada GRADE_MIN min)."""
    return dict(result=await grade_once(), summary=REC.summary())

@app.get("/api/record/game/{league}/{eid}")
async def record_game(league: str, eid: str):
    return dict(rows=REC.game_rows(league, eid))

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
    return dict(ok=True, grading=dict(GRADE_STATE, every_min=GRADE_MIN), record=REC.summary(), cache=STATS, ratings={k: v["n_games"] for k, v in ratings._ratings.items()}, ts=time.time(), snapshots=dict(SNAP_STATE, every_min=SNAP_MIN, db=history.stats()))

app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC, "index.html"), headers={"Cache-Control": "no-cache"})
