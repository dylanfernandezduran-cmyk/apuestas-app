import asyncio, os, time
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import data, ratings
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

@app.get("/api/sports")
async def sports():
    return [dict(s, leagues=[dict(key=k, name=LEAGUES[k]["name"]) for k in s["leagues"]]) for s in SPORTS]

@app.get("/api/games")
async def games(league: str, days: int | None = None):
    if league not in LEAGUES: raise HTTPException(404, "Liga no soportada")
    gs, ok = await data.list_games(league, days)
    return dict(league=league, name=LEAGUES[league]["name"], ok=ok, games=gs, now=time.time())

@app.get("/api/game/{league}/{eid}")
async def game(league: str, eid: str):
    if league not in LEAGUES: raise HTTPException(404, "Liga no soportada")
    r = await data.analyze(league, eid)
    if not r: raise HTTPException(404, "Juego no encontrado o sin datos")
    return r

@app.get("/api/picks")
async def picks(scope: str = "24h"):
    return await data.picks(scope)

@app.get("/api/health")
async def health():
    return dict(ok=True, cache=STATS, ratings={k: v["n_games"] for k, v in ratings._ratings.items()}, ts=time.time())

app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC, "index.html"), headers={"Cache-Control": "no-cache"})
