"""Pegamento: arma los bloques nuevos (en vivo, lesiones, clima, alineaciones, descanso) a partir de ESPN/Open-Meteo.
Cada bloque es independiente: si una fuente falla, sólo ese bloque queda en 'sin dato' (nunca se inventa ni se rompe el detalle)."""
import asyncio, time
from datetime import timedelta
from .cache import get_json
from .config import ESPN, LEAGUES
from . import data as D, live as LV, injuries as INJ, weather as WX, lineups as LU, ratings as RT

SUMMARY_TTL = 30

def rest_info(recent, game_iso, fam):
    """Días de descanso (días completos sin jugar) y juegos en los últimos 7 días, con resultados reales ya jugados. recent: filas [{date,...}] (cualquier orden)."""
    gd = D.parse_dt(game_iso)
    if not gd or not recent: return None
    gday = gd.astimezone(D.CDMX).date()
    days = []
    for r in recent:
        d = D.parse_dt(r.get("date"))
        if d:
            dd = d.astimezone(D.CDMX).date()
            if dd < gday: days.append(dd)
    if not days: return None
    last = max(days)
    rest = (gday - last).days - 1
    n7 = sum(1 for d in days if (gday - d).days <= 7)
    return dict(days=rest, b2b=(rest == 0 and fam in ("basketball", "hockey")), n7=n7, last=last.isoformat())

def _row_inj(by_team, tid):
    return (by_team.get(str(tid)) or {}).get("entries") or []

async def list_injury_counts(league, games):
    """{eid: {home:{out,doubt,dtd}, away:{...}}} para las tarjetas de la lista. {} si la liga no publica lesiones."""
    by, ts, ok = await INJ.league_injuries(league)
    if not ok: return {}, False
    out = {}
    for g in games:
        out[g["id"]] = {s: INJ.counts(_row_inj(by, g[s]["id"])) for s in ("home", "away")}
    return out, True

async def _lineup_block(league, fam, summ, game, R, inj_by, state):
    """Alineaciones por equipo: confirmadas (ESPN) o proyectadas (último juego real) + cambios guardados en SQLite."""
    if fam == "tennis": return None
    res = dict(kind=fam, sides={}, supported=True)
    if fam == "football":
        for s in ("home", "away"):
            tid = game[s]["id"]
            res["sides"][s] = dict(status="profundidad", depth=await LU.depth_chart(league, tid))
        res["note"] = "Depth chart de ESPN (titular por posición). ESPN no publica inactivos/activos oficiales en este endpoint: no es una alineación confirmada."
        return res
    for s in ("home", "away"):
        tid = game[s]["id"]
        st = LU.starters_from_summary(summ, fam, tid) if summ else None
        if st and (st.get("players") or st.get("goalie")) and not (fam == "hockey" and state == "pre"):
            side = dict(status="confirmado", **st)
        else:
            side = dict(status="sin_publicar")
            if state == "pre":
                recent = RT.team_summary(R, tid)["recent"] if R else []
                prj, dt, eid = await LU.last_game_starters(league, fam, tid, recent)
                if prj: side = dict(status="proyectado", from_date=dt, from_eid=eid, **prj)
        if fam == "baseball":
            pp = LU.probable_pitcher(summ, tid) if summ else None
            if pp: side["pitcher"] = pp
        # marca jugadores reportados con lesión en el reporte actual
        injd = {e["id"]: e for e in _row_inj(inj_by, tid)} if inj_by else {}
        for p in (side.get("players") or []) + ([side["goalie"]] if side.get("goalie") else []):
            e = injd.get(p["id"])
            if e: p["inj"] = e["status_es"]
        pls = (side.get("players") or []) + ([side["goalie"]] if side.get("goalie") else [])
        if pls and side["status"] in ("confirmado", "proyectado"):
            ch, since = LU.track(league, game["id"], tid, side["status"], pls)
            if side["status"] == "confirmado" and ch: side["changes"] = ch; side["changes_since"] = since
        res["sides"][s] = side
    if all(v["status"] == "sin_publicar" for v in res["sides"].values()) and state != "pre": res["note"] = "ESPN no publicó titulares de este juego."
    return res

async def detail(out, league, eid):
    """Agrega al análisis: live, prov, injuries_full, weather, lineups, rest, updated. Modifica y devuelve `out`."""
    cfg = LEAGUES[league]; fam = cfg["family"]; g = out["game"]
    out["updated"] = time.time()
    summ = None
    if fam != "tennis":
        summ = await get_json(f"{ESPN}/{cfg['path']}/summary", ttl=SUMMARY_TTL, params={"event": eid})
    # --- en vivo
    try:
        if fam == "tennis":
            if g["state"] != "pre": out["live"] = dict(state=g["state"], text=g.get("status"), linescores=None, stats=[], plays=[], situation=None)
        else:
            out["live"] = LV.live_detail(summ, fam, league, g)
        out["prov"] = LV.provisional(out.get("record") or [], g, fam)
    except Exception as ex:
        out["live"] = None; out["prov"] = {}
    # --- descanso
    try:
        R = await RT.get_ratings(league) if fam != "tennis" else None
        if R:
            out["rest"] = {}
            for s in ("home", "away"):
                ri = rest_info(RT.team_summary(R, g[s]["id"], limit=12)["recent"], g["date"], fam)
                if ri: out["rest"][s] = ri
    except Exception:
        R = None
    # --- lesiones (reporte de liga + seguimiento) con respaldo del summary
    inj_by = {}
    if fam != "tennis":
        try:
            inj_by, ts, supported = await INJ.league_injuries(league)
            lead = out.get("leaders") or {}
            full = {}
            for s in ("home", "away"):
                tid = g[s]["id"]
                entries = _row_inj(inj_by, tid)
                if not entries and out.get("injuries", {}).get(tid):    # respaldo: lista del summary
                    entries = [dict(e, bucket=INJ.bucket(e["status"]) or "dtd", status_es=INJ.status_es(e["status"])) for e in out["injuries"][tid]]
                keys = {l["id"] for l in lead.get(tid, [])}
                full[s] = INJ.team_payload(league, tid, entries, keys)
            out["injuries_full"] = dict(sides=full, supported=bool(supported or any(full[s]["entries"] for s in full)), fetched=ts, tracking_since=INJ.tracking_since(league),
                                        source="ESPN")
        except Exception:
            out["injuries_full"] = None
    else:
        out["injuries_full"] = dict(sides={}, supported=False, tennis=True)
    # --- clima (Open-Meteo)
    try:
        comp = (summ or {}).get("header", {}).get("competitions", [{}])[0] if summ else {}
        v = ((summ or {}).get("gameInfo") or {}).get("venue") or {}
        addr = v.get("address") or {}
        gg = dict(g, venue=v.get("fullName") or g.get("venue"), venue_city=addr.get("city"), venue_state=addr.get("state"), venue_country=addr.get("country"), indoor=v.get("indoor"))
        out["weather"] = await WX.game_weather(gg, fam, D.parse_dt(g["date"]))
        espn_wx = (summ or {}).get("gameInfo", {}).get("weather") if summ else None
        if espn_wx and out["weather"].get("status") == "sin_dato" and espn_wx.get("temperature") is not None:
            out["weather"]["espn"] = dict(temp_f=espn_wx.get("temperature"), gust=espn_wx.get("gust"), precip=espn_wx.get("precipitation"))
    except Exception:
        out["weather"] = dict(status="sin_dato", reason="Error al consultar el clima")
    # --- alineaciones
    try:
        out["lineups"] = await _lineup_block(league, fam, summ, g, R, inj_by, g["state"])
    except Exception:
        out["lineups"] = None
    return out

async def lineup_snapshot(league, g):
    """Para el bucle de fondo: guarda la foto de alineación del juego (list-game dict) sin armar todo el detalle."""
    cfg = LEAGUES[league]; fam = cfg["family"]
    summ = await get_json(f"{ESPN}/{cfg['path']}/summary", ttl=SUMMARY_TTL, params={"event": g["id"]})
    if not summ: return None
    R = await RT.get_ratings(league)
    inj_by, ts, ok = await INJ.league_injuries(league)
    return await _lineup_block(league, fam, summ, g, R, inj_by, g["state"])
