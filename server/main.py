import asyncio, os, time
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from . import imgproxy, search as SEARCH, data, ratings, market as MK, history, record as REC, prediction as PRED, grading, enrich, injuries as INJ, weather as WX, live as LV, props as PROPS, chat as CHAT, tickets as TK
from .cache import get_json
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
    asyncio.create_task(injuries_loop())
    asyncio.create_task(lineups_loop())

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
    try: r["pred"] = await PRED.grade_pending()
    except Exception as ex: r["pred"] = dict(err=str(ex)[:80])
    try: r["tickets"] = await TK.grade_pending()
    except Exception as ex: r["tickets"] = dict(err=str(ex)[:80])
    GRADE_STATE.update(last=time.time(), runs=GRADE_STATE["runs"] + 1, graded=GRADE_STATE["graded"] + r["graded"] + r["void"], last_result=r, err=None)
    return r

async def grade_loop():
    await asyncio.sleep(20)
    while True:
        try: await grade_once()
        except Exception as ex: GRADE_STATE["err"] = str(ex)[:200]
        await asyncio.sleep(max(60, GRADE_MIN * 60))

INJ_MIN = float(os.environ.get("INJ_MIN", "10"))
INJ_STATE = {"last": None, "runs": 0, "err": None}

async def injuries_loop():
    """Sigue el reporte de lesiones de cada liga para detectar regresos (nuevo/mejora/sale del reporte) y los guarda en SQLite."""
    await asyncio.sleep(30)
    while True:
        try:
            for l, cfg in LEAGUES.items():
                if cfg["family"] in ("tennis", "soccer"): continue
                try: await INJ.league_injuries(l)
                except Exception: pass
            INJ_STATE.update(last=time.time(), runs=INJ_STATE["runs"] + 1, err=None)
        except Exception as ex: INJ_STATE["err"] = str(ex)[:200]
        await asyncio.sleep(max(120, INJ_MIN * 60))

LU_STATE = {"last": None, "runs": 0, "games": 0, "err": None}

async def lineups_loop():
    """Cada 10 min guarda la foto de alineaciones de los juegos que empiezan en las próximas 4 h (para detectar cambios de último momento)."""
    await asyncio.sleep(60)
    while True:
        try:
            now = datetime.now(timezone.utc); n = 0
            for l, cfg in LEAGUES.items():
                if cfg["family"] in ("tennis", "football"): continue
                try: gs, ok = await data.list_games(l, 0)
                except Exception: continue
                for g in gs:
                    d = data.parse_dt(g["date"])
                    if g["state"] in ("pre", "in") and d and now - timedelta(hours=1) <= d <= now + timedelta(hours=4):
                        try: await enrich.lineup_snapshot(l, g); n += 1
                        except Exception: pass
            LU_STATE.update(last=time.time(), runs=LU_STATE["runs"] + 1, games=n, err=None)
        except Exception as ex: LU_STATE["err"] = str(ex)[:200]
        await asyncio.sleep(600)

@app.get("/api/img")
async def img(u: str, w: int = 64):
    """Logo/foto de ESPN reducido y cacheado (sólo hosts de imágenes de ESPN). 404 si no existe -> el frontend muestra iniciales."""
    if not imgproxy.validate(u): raise HTTPException(400, "url de imagen no permitida")
    r = await imgproxy.get_image(u, w)
    if not r: raise HTTPException(404, "sin imagen")
    return Response(r[0], media_type=r[1] or "image/png", headers={"Cache-Control": "public, max-age=604800"})

@app.get("/api/search")
async def search(q: str = ""):
    """Buscador del inicio (juegos, equipos, jugadores de tenis, ligas/torneos) sobre los juegos cargados de todas las ligas."""
    if len(SEARCH.norm(q)) < 2 or len(q) > 60: return dict(q=q, leagues=[], teams=[], games=[])
    leagues = list(LEAGUES.keys())
    lists = await asyncio.gather(*[data.list_games(l) for l in leagues], return_exceptions=True)
    by = {l: (r[0] if not isinstance(r, Exception) else []) for l, r in zip(leagues, lists)}
    return SEARCH.search(q, by, LEAGUES, SPORTS)

@app.get("/api/sports")
async def sports():
    return [dict(s, leagues=[dict(key=k, name=LEAGUES[k]["name"]) for k in s["leagues"]]) for s in SPORTS]

def _rec_short(r):
    return dict(market=r["market"], selection=r["selection"], line=r.get("line"), type=r["type"], status=r["status"], label=r["label"])

@app.get("/api/games")
async def games(league: str, days: int | None = None):
    if league not in LEAGUES: raise HTTPException(404, "Liga no soportada")
    gs, ok = await data.list_games(league, days)
    try:
        rr = REC.games_rows(league, [g["id"] for g in gs])
        fam = LEAGUES[league]["family"]
        for g in gs:
            g["rec"] = [_rec_short(r) for r in rr.get(g["id"], [])]
            if g["state"] == "in": g["prov"] = LV.provisional(g["rec"], g, fam)
    except Exception: pass
    inj_ok = None
    try:
        inj, inj_ok = await asyncio.wait_for(enrich.list_injury_counts(league, [g for g in gs if g["state"] != "post"]), 6)
        for g in gs:
            if g["id"] in inj: g["inj"] = inj[g["id"]]
    except Exception: pass
    return dict(league=league, name=LEAGUES[league]["name"], ok=ok, games=gs, now=time.time(), inj_supported=inj_ok)

@app.get("/api/live")
async def live(league: str | None = None):
    """Juegos en vivo (marcador, reloj, situación) + calificación PROVISIONAL de nuestros picks. Ligero: se consulta cada ~25 s mientras haya juegos en vivo."""
    leagues = [league] if league else list(LEAGUES.keys())
    lists = await asyncio.gather(*[data.list_games(l) for l in leagues], return_exceptions=True)
    out = []
    for l, r in zip(leagues, lists):
        if isinstance(r, Exception): continue
        live_g = [g for g in r[0] if g["state"] == "in"]
        if not live_g: continue
        rr = REC.games_rows(l, [g["id"] for g in live_g])
        for g in live_g:
            g["rec"] = [_rec_short(x) for x in rr.get(g["id"], [])]
            g["prov"] = LV.provisional(g["rec"], g, LEAGUES[l]["family"])
            out.append(g)
    return dict(games=out, n=len(out), now=time.time())

_home_cache = {}

@app.get("/api/home")
async def home():
    """Resumen del día: en vivo, mejores picks de hoy, récord, bajas confirmadas en juegos de hoy y acceso por deporte."""
    ent = _home_cache.get("h")
    if ent and time.time() - ent[0] < 20: return ent[1]
    leagues = list(LEAGUES.keys())
    lists = await asyncio.gather(*[data.list_games(l) for l in leagues], return_exceptions=True)
    today = data.now_cdmx().strftime("%Y-%m-%d")
    live_g, sports = [], {s["key"]: dict(key=s["key"], name=s["name"], emoji=s["emoji"], today=0, live=0) for s in SPORTS}
    inj_targets = {}
    for l, r in zip(leagues, lists):
        if isinstance(r, Exception): continue
        fam = LEAGUES[l]["family"]
        for g in r[0]:
            sp = sports[LEAGUES[l]["sport"]]
            if g["state"] == "in":
                sp["live"] += 1; sp["today"] += 1; live_g.append(g)
            elif g["state"] == "pre" and (data.local_date_str(g["date"]) or "") == today:
                sp["today"] += 1
                if fam not in ("tennis", "soccer"): inj_targets.setdefault(l, []).append(g)
    for g in live_g:
        rr = REC.games_rows(g["league"], [g["id"]]).get(g["id"], [])
        g["rec"] = [_rec_short(x) for x in rr]
        g["prov"] = LV.provisional(g["rec"], g, LEAGUES[g["league"]]["family"])
    # bajas confirmadas de equipos que juegan hoy (QB primero en NFL; sin inventar "clave")
    inj = []
    for l, gs in inj_targets.items():
        try:
            by, ts, ok = await INJ.league_injuries(l)
        except Exception: continue
        for g in gs[:12]:
            for sd in ("away", "home"):
                tm = by.get(str(g[sd]["id"])) or {}
                outs = [e for e in tm.get("entries", []) if e["bucket"] == "out"]
                outs.sort(key=lambda e: (e["pos"] != "QB", e["name"] or ""))
                for e in outs[:1]:
                    inj.append(dict(league=l, id=g["id"], team=g[sd]["short"], name=e["name"], pos=e["pos"], status=e["status_es"], detail=e["detail"], n_out=len([x for x in tm["entries"] if x["bucket"] == "out"])))
    inj.sort(key=lambda e: (e["pos"] != "QB", -e["n_out"]))
    res = dict(live=live_g, record=REC.summary(days=30), record_all=REC.summary(), record_main=REC.summary(typ="main"), injuries=inj[:6], sports=list(sports.values()), now=time.time())
    _home_cache["h"] = (time.time(), res)
    return res

_wx_cache = {}

@app.get("/api/league_wx")
async def league_wx(league: str, hours: int = 96):
    """Clima compacto (Open-Meteo) de los juegos próximos al aire libre de la liga: para las tarjetas de lista."""
    if league not in LEAGUES: raise HTTPException(404, "Liga no soportada")
    fam = LEAGUES[league]["family"]
    if fam not in WX.OUTDOOR_FAMILIES: return dict(league=league, items={}, now=time.time())
    ent = _wx_cache.get(league)
    if ent and time.time() - ent[0] < 600: return ent[1]
    gs, ok = await data.list_games(league)
    gs = [g for g in gs if g["state"] in ("pre", "in")][:30]
    sem = asyncio.Semaphore(4)
    async def one(g):
        async with sem:
            try:
                w = await WX.game_weather(g, fam, data.parse_dt(g["date"]))
            except Exception:
                return g["id"], None
        keep = ("status", "roof", "temp_c", "wind_kmh", "wind_from", "precip_prob", "icon", "text")
        return g["id"], dict({k: w.get(k) for k in keep}, notes=len(w.get("notes") or []), warn=bool(w.get("notes")))
    res = dict(league=league, items=dict(await asyncio.gather(*[one(g) for g in gs])), now=time.time())
    _wx_cache[league] = (time.time(), res)
    return res

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
    if not r: raise HTTPException(404, "Juego no encontrado o la fuente (ESPN) no respondió. Reintenta en unos segundos.")
    try: await enrich.detail(r, league, eid)
    except Exception: pass
    return r

@app.get("/api/props/{league}/{eid}")
async def game_props(league: str, eid: str):
    """Props de jugadores del juego (DraftKings vía ESPN; si aún no hay, líderes con referencia calculada y rotulada). Datos reales, nada inventado."""
    if league not in LEAGUES: raise HTTPException(404, "Liga no soportada")
    try: return await PROPS.game_props(league, eid)
    except Exception as e: raise HTTPException(502, f"No se pudieron cargar los props: {type(e).__name__}")

@app.get("/api/prop/{league}/{eid}/{aid}/{key}")
async def player_prop(league: str, eid: str, aid: str, key: str, hist: int = 10):
    if league not in LEAGUES: raise HTTPException(404, "Liga no soportada")
    if not aid.isdigit(): raise HTTPException(400, "Jugador inválido")
    try: r = await PROPS.player_prop(league, eid, aid, key, hist=min(max(hist, 0), 20))
    except Exception as e: raise HTTPException(502, f"No se pudo cargar el prop: {type(e).__name__}")
    if not r: raise HTTPException(404, "Prop no disponible para este jugador")
    return r

@app.get("/api/chat/status")
async def chat_status():
    return CHAT.status()

@app.post("/api/chat")
async def chat(body: dict):
    q = str((body or {}).get("q") or "").strip()
    if not q: raise HTTPException(400, "Pregunta vacía")
    return await CHAT.answer(q, (body or {}).get("league"), (body or {}).get("eid"))

@app.get("/api/record")
async def record(sport: str | None = None, type: str | None = None, days: int | None = None, limit: int = 60, basis: str | None = None):
    """Récord de picks: resumen (G-P-E, %, unidades a 1u plano con la cuota registrada) + últimos calificados. Filtros: sport, type=main|suggestion, days."""
    return dict(summary=REC.summary(sport, type, days, basis), recent=REC.query(sport, type, days, min(max(limit, 1), 300), basis=basis), grading=dict(GRADE_STATE, every_min=GRADE_MIN),
                filters=dict(sport=sport, type=type, days=days, basis=basis), pred=PRED.stats(sport, days), now=time.time())

@app.post("/api/grade")
async def grade_now():
    """Califica ahora lo pendiente (también corre solo cada GRADE_MIN min)."""
    return dict(result=await grade_once(), summary=REC.summary())

@app.get("/api/record/day")
async def record_day(date: str | None = None):
    """Récord de UN día (fecha del juego en hora CDMX, default hoy) + calendario de días con su G-P (pt92u)."""
    import re as _re
    today = REC.cdmx_date()
    date = date or today
    if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", date): raise HTTPException(400, "Fecha inválida (AAAA-MM-DD)")
    return dict(date=date, today=today, days=REC.days(), **REC.day(date),
                cumulative=REC.summary(typ="main"), cumulative_all=REC.summary(),
                cumulative_suggestion=REC.summary(typ="suggestion"),
                grading=dict(GRADE_STATE, every_min=GRADE_MIN), now=time.time())

# ---------------- tickets / parlays de papel
@app.get("/api/tickets")
async def tickets_list(date: str | None = None):
    import re as _re
    today = REC.cdmx_date(); date = date or today
    if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", date): raise HTTPException(400, "Fecha inválida (AAAA-MM-DD)")
    return dict(today=today, **TK.by_day(date))

@app.post("/api/tickets")
async def tickets_create(body: dict):
    r = TK.create((body or {}).get("legs"), (body or {}).get("name"), (body or {}).get("source") or "app")
    if not r["ok"]: raise HTTPException(400, " · ".join(r["errors"]))
    return r

@app.post("/api/tickets/check")
async def tickets_check(body: dict):
    legs = (body or {}).get("legs") or []
    return dict(**TK.check(legs), **(TK.combine(legs) if legs and all(l.get("odds") is not None for l in legs) else {}))

@app.delete("/api/tickets/{tid}")
async def tickets_delete(tid: int):
    if not TK.delete(tid): raise HTTPException(404, "No existe o ya se calificó")
    return dict(ok=True)

@app.get("/api/parlay/suggest")
async def parlay_suggest(n: int = 3, scope: str = "hoy", sport: str | None = None):
    return await TK.suggest(n, scope, sport)

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

def _lan_ipv4():
    """IPv4 de LAN (no loopback). Preferida: la que enruta a la gateway típica; si falla, la primera no-loopback."""
    import socket
    # 1) UDP connect trick: no envía paquetes, solo elige interfaz de salida
    for probe in ("192.168.100.1", "8.8.8.8"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.3)
            s.connect((probe, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass
    # 2) hostname resolve
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                return ip
    except Exception:
        pass
    return None

@app.get("/api/lan")
async def lan():
    """IP/URL LAN actuales + hostname .local (estable ante DHCP). Sin secretos."""
    import socket
    ip = _lan_ipv4()
    host = (socket.gethostname() or "DESKTOP-NOG66RU").split(".")[0]
    local = f"http://{host}.local:8765"
    by_ip = f"http://{ip}:8765" if ip else None
    return dict(ok=True, ip=ip, port=8765, hostname=host, url_local=local, url_ip=by_ip, preferred=local)

@app.get("/api/health")
async def health():
    return dict(ok=True, grading=dict(GRADE_STATE, every_min=GRADE_MIN), record=REC.summary(), cache=STATS, ratings={k: v["n_games"] for k, v in ratings._ratings.items()}, ts=time.time(), snapshots=dict(SNAP_STATE, every_min=SNAP_MIN, db=history.stats()), injuries=dict(INJ_STATE, every_min=INJ_MIN), lineups=LU_STATE)

app.mount("/static", StaticFiles(directory=STATIC), name="static")

# ------------------------------------------------------------------ marca (nombre/logo intercambiables: static/brand/brand.json) + PWA
import json as _json

def brand():
    d = _json.load(open(os.path.join(STATIC, "brand", "brand.json"), encoding="utf-8"))
    act = os.environ.get("BRAND") or d["active"]
    if act not in d["options"]: act = d["active"]
    o = d["options"][act]
    return dict(id=act, name=o["name"], short=o.get("short", o["name"]), tagline=o["tagline"], palette=o.get("palette") or {}, theme=d["theme"], options={k: dict(v) for k, v in d["options"].items()})

def _bg(b):
    """Fondo de la marca activa: palette.bg si existe, si no theme.bg (manifest, theme-color, splash)."""
    return (b.get("palette") or {}).get("bg") or b["theme"]["bg"]

def _theme_css(pal):
    """Paleta opcional por marca (brand.json -> options.<id>.palette) -> variables CSS. Sin paleta = colores por defecto de style.css."""
    if not pal: return ""
    def rgb(h):
        h = h.lstrip("#"); return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    names = dict(acc="acc", grn="grn", red="red", amb="amb", blu="blu", live="live", ink="ink", bg="bg", panel="panel", panel2="panel2", hair="hair", line="line")
    norgb = ("ink", "panel", "panel2", "hair", "line")
    out = []
    for k, v in pal.items():
        if k in names and isinstance(v, str) and len(v) == 7 and v.startswith("#"):
            out.append(f"--{k}:{v}")
            if k not in norgb: out.append(f"--{k}-rgb:{rgb(v)}")
    return ":root{" + ";".join(out) + "}" if out else ""

@app.get("/api/brand")
async def brand_api():
    return brand()

@app.get("/manifest.webmanifest")
async def manifest():
    b = brand(); i = "/static/brand/icons/"
    return JSONResponse(dict(name=f"{b['name']} · picks deportivos", short_name=b["short"], description=b["tagline"], start_url="/", scope="/", display="standalone",
                             orientation="portrait", background_color=_bg(b), theme_color=_bg(b), lang="es-MX",
                             icons=[dict(src=i + "icon-192.png", sizes="192x192", type="image/png", purpose="any"), dict(src=i + "icon-512.png", sizes="512x512", type="image/png", purpose="any"),
                                    dict(src=i + "maskable-512.png", sizes="512x512", type="image/png", purpose="maskable"), dict(src=i + "apple-touch-icon.png", sizes="180x180", type="image/png")]),
                        media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})

@app.get("/sw.js")
async def service_worker():
    return FileResponse(os.path.join(STATIC, "sw.js"), media_type="application/javascript", headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})

@app.get("/")
async def index():
    from fastapi.responses import HTMLResponse
    b = brand()
    html = open(os.path.join(STATIC, "index.html"), encoding="utf-8").read()
    glyph = open(os.path.join(STATIC, "brand", b["id"], "glyph.svg"), encoding="utf-8").read()
    for k, v in (("__NAME__", b["name"]), ("__SHORT__", b["short"]), ("__TAGLINE__", b["tagline"]), ("__BRAND_ID__", b["id"]), ("__GLYPH__", glyph), ("__BG__", _bg(b)), ("__THEME__", _theme_css(b["palette"]))):
        html = html.replace(k, v)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})
