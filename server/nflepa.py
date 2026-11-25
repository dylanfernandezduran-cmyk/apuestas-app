"""NFL EPA/jugada por equipo desde nflverse (play-by-play público, GitHub releases).
EPA neta = EPA/jugada ofensiva − EPA/jugada permitida (pases + carreras), encogida por n/(n+k).
Backtest walk-forward (research/backtest_nfl_epa.json): mejora Brier y log loss fuera de muestra en 2025 y 2026,
así que entra al modelo de margen con NFL_EPA_COEF puntos por unidad de EPA neta. Si la descarga falla, no se usa nada."""
import asyncio, csv, gzip, io, os, time
from datetime import datetime
from pathlib import Path
import httpx

URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{y}.csv.gz"
import tempfile
CACHE = Path(os.environ.get("NRNM_CACHE_DIR") or Path(tempfile.gettempdir()) / "nrnm-cache")   # fuera de data/ (no se publica en Pages)
TTL = 12 * 3600
K = 6
ABBR = {"LA": "LAR", "WAS": "WSH"}   # nflverse → ESPN
_MEM = {}

def season_now(now=None):
    d = datetime.fromtimestamp(now or time.time()); return d.year if d.month >= 8 else d.year - 1

def parse(raw):
    off, de, games, pas = {}, {}, {}, {}
    with gzip.open(io.BytesIO(raw), "rt", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("season_type") != "REG" or r.get("play_type") not in ("pass", "run"): continue
            e, p, d = r.get("epa"), r.get("posteam"), r.get("defteam")
            if not p or not d or e in ("", "NA", None): continue
            e = float(e); p = ABBR.get(p, p); d = ABBR.get(d, d)
            a = off.setdefault(p, [0.0, 0]); a[0] += e; a[1] += 1
            b = de.setdefault(d, [0.0, 0]); b[0] += e; b[1] += 1
            if r["play_type"] == "pass": c = pas.setdefault(p, [0.0, 0]); c[0] += e; c[1] += 1
            games.setdefault(p, set()).add(r["game_id"])
    out = {}
    for t in off:
        if t not in de: continue
        ng = len(games.get(t, ()))
        o = off[t][0] / off[t][1]; dd = de[t][0] / de[t][1]
        out[t] = dict(off=round(o, 3), deff=round(dd, 3), net=round(o - dd, 3), net_shrunk=(o - dd) * ng / (ng + K),
                      pass_off=round(pas[t][0] / pas[t][1], 3) if t in pas and pas[t][1] else None, games=ng, plays=off[t][1])
    return out

async def table(season=None):
    season = season or season_now()
    m = _MEM.get(season)
    if m and time.time() - m[0] < TTL: return m[1]
    CACHE.mkdir(parents=True, exist_ok=True)
    fp = CACHE / f"nfl_pbp_{season}.csv.gz"
    raw = None
    if fp.exists() and time.time() - fp.stat().st_mtime < TTL:
        raw = fp.read_bytes()
    else:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60) as c:
                r = await c.get(URL.format(y=season))
            if r.status_code == 200 and r.content[:2] == b"\x1f\x8b":
                raw = r.content; fp.write_bytes(raw)
        except Exception:
            raw = None
        if raw is None and fp.exists(): raw = fp.read_bytes()   # respaldo: última copia descargada
    if raw is None: return None
    t = await asyncio.to_thread(parse, raw)
    _MEM[season] = (time.time(), t)
    return t
