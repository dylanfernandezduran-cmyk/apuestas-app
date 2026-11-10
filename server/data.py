"""Obtención de datos reales (ESPN + MLB StatsAPI) y armado de análisis por juego."""
import asyncio, re, time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .cache import get_json
from .config import ESPN, MLB_API, LEAGUES, FAMILY, TZ, SPORTS
from .odds import extract_odds, fmt_am
from . import ratings as RT
from . import model as M
from . import market as MK
from . import probs as PR
from . import prediction as PRED
from . import record as REC
from . import live as LV

CDMX = ZoneInfo(TZ)
SD = "Sin dato"

def now_cdmx(): return datetime.now(CDMX)

def parse_dt(s):
    if not s: return None
    s = s.replace("Z", "+00:00")
    if len(s) == 17 and s.endswith("+00:00") is False and "T" in s: s += ":00"
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        try: return datetime.strptime(s[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        except Exception: return None

def logo_of(team):
    return team.get("logo") or ((team.get("logos") or [{}])[0].get("href"))

def _rec(c):
    for r in c.get("records") or []:
        if r.get("type") == "total" or r.get("name") == "overall": return r.get("summary")
    return (c.get("records") or [{}])[0].get("summary") if c.get("records") else None

# ------------------------------------------------------------------ listas de juegos
def _game_from_event(league, e):
    comp = e["competitions"][0]
    hc = next((c for c in comp["competitors"] if c["homeAway"] == "home"), None)
    ac = next((c for c in comp["competitors"] if c["homeAway"] == "away"), None)
    if not hc or not ac: return None
    st = comp["status"]["type"]
    def side(c):
        t = c["team"]
        return dict(id=t["id"], name=t.get("displayName"), short=t.get("shortDisplayName") or t.get("displayName"),
                    abbr=t.get("abbreviation"), logo=logo_of(t), score=c.get("score") if not isinstance(c.get("score"), dict) else c["score"].get("displayValue"),
                    record=_rec(c), winner=c.get("winner"))
    g = dict(id=e["id"], league=league, league_name=LEAGUES[league]["name"], sport=LEAGUES[league]["sport"], date=comp.get("date") or e["date"],
             state=st["state"], status=st.get("shortDetail") or st.get("description"), home=side(hc), away=side(ac),
             venue=(comp.get("venue") or {}).get("fullName"), neutral=bool(comp.get("neutralSite")),
             note=(comp.get("notes") or [{}])[0].get("headline") if comp.get("notes") else None, tv=comp.get("broadcast"))
    va = (comp.get("venue") or {}).get("address") or {}
    g.update(venue_city=va.get("city"), venue_state=va.get("state"), venue_country=va.get("country"), indoor=(comp.get("venue") or {}).get("indoor"))
    if st["state"] in ("in", "post"):
        g["status"] = LV.status_es(LEAGUES[league]["family"], league, comp["status"])
    if st["state"] == "in":
        try:
            g["live"] = LV.live_core(comp, LEAGUES[league]["family"], league, {str(c["team"]["id"]): c["team"].get("abbreviation") for c in comp["competitors"]})
        except Exception:
            g["live"] = None
    o = None
    if st["state"] == "pre" and comp.get("odds"):
        o = extract_odds(comp["odds"][0])
    g["odds"] = _brief_odds(o)
    return g

def _brief_odds(o):
    if not o: return None
    return dict(book=o["book"], ml=o["ml"], spread=o["spread"], total=o["total"])

def local_date_str(iso):
    d = parse_dt(iso)
    return d.astimezone(CDMX).strftime("%Y-%m-%d") if d else None

async def _list_games(league, days=None, include_past_today=True):
    cfg = LEAGUES[league]
    if cfg["family"] == "tennis": return await tennis_games(league)
    days = cfg["days"] if days is None else days
    today = now_cdmx().date()
    dates = [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(0, days + 1)]
    res = await asyncio.gather(*[get_json(f"{ESPN}/{cfg['path']}/scoreboard", ttl=(20 if d == dates[0] else 90), params={"dates": d}) for d in dates])
    seen = {}; ok = False
    for d in res:
        if not d: continue
        ok = True
        for e in d.get("events", []):
            try:
                g = _game_from_event(league, e)
            except Exception:
                g = None
            if g: seen[g["id"]] = g
    t0 = today.strftime("%Y-%m-%d")
    out = [g for g in seen.values() if (local_date_str(g["date"]) or "") >= t0]
    if not include_past_today: out = [g for g in out if g["state"] == "pre"]
    out.sort(key=lambda g: g["date"])
    return out, ok

# ------------------------------------------------------------------ tenis
async def tennis_rankings(league):
    d = await get_json(f"{ESPN}/{LEAGUES[league]['path']}/rankings", ttl=21600)
    m = {}
    try:
        for r in d["rankings"][0]["ranks"]:
            a = r["athlete"]; m[str(a["id"])] = dict(rank=r["current"], points=r.get("points"), name=a.get("displayName"))
    except Exception: pass
    return m

async def tennis_events(league):
    d = await get_json(f"{ESPN}/{LEAGUES[league]['path']}/scoreboard", ttl=30)
    return (d or {}).get("events", []), d is not None

HEADSHOT = "https://a.espncdn.com/i/headshots/tennis/players/full/{}.png"

def _t_side(c, rk):
    a = c.get("athlete") or {}
    aid = str(c.get("id") or "")
    r = rk.get(aid, {})
    return dict(id=aid, name=a.get("displayName") or SD, short=a.get("shortName") or a.get("displayName"), abbr=None,
                logo=(HEADSHOT.format(aid) if aid else None), flag=(a.get("flag") or {}).get("href"), country=(a.get("flag") or {}).get("alt"), rank=r.get("rank"), points=r.get("points"),
                score=None, winner=c.get("winner"), sets=[int(x["value"]) for x in c.get("linescores", []) if x.get("value") is not None],
                record=(f"#{r['rank']} ATP/WTA" if r.get("rank") else None))

async def list_games(league, days=None, include_past_today=True):
    r = await _list_games(league, days, include_past_today)
    try:
        from . import record as _rec_mod
        _rec_mod.remember_logos(league, r[0] if isinstance(r, tuple) else r)
    except Exception:
        pass
    return r

async def tennis_games(league):
    evs, ok = await tennis_events(league)
    rk = await tennis_rankings(league)
    out = []
    today = now_cdmx().strftime("%Y-%m-%d")
    last = (now_cdmx() + timedelta(days=4)).strftime("%Y-%m-%d")
    for e in evs:
        for gr in e.get("groupings", []):
            if "Singles" not in gr["grouping"]["displayName"]: continue
            for c in gr["competitions"]:
                cs = c.get("competitors", [])
                if len(cs) != 2 or not all(x.get("athlete") for x in cs): continue
                if not (today <= (local_date_str(c["date"]) or "") <= last): continue
                st = c["status"]["type"]
                a, b = sorted(cs, key=lambda x: x.get("order", 9))
                out.append(dict(id=str(c["id"]), league=league, league_name=LEAGUES[league]["name"], sport="tenis", date=c["date"], state=st["state"],
                                status=st.get("shortDetail"), home=_t_side(a, rk), away=_t_side(b, rk), venue=(c.get("venue") or {}).get("fullName"),
                                court=(c.get("venue") or {}).get("court"), neutral=True, tournament=e.get("name"),
                                note=f"{e.get('name')} · {(c.get('round') or {}).get('displayName', '')}".strip(" ·"), odds=None, tv=None,
                                round=(c.get("round") or {}).get("displayName"),
                                best_of=(5 if (league == "atp" and re.search(r"Australian Open|Roland Garros|French Open|Wimbledon|US Open", e.get("name") or "", re.I)) else 3)))
                if st["state"] == "in":
                    srv = next((("home" if x.get("homeAway") == "home" else "away") for x in (a, b) if x.get("possession") is True or x.get("serving") is True or x.get("isServing") is True), None)
                    out[-1]["live"] = dict(text=LV.status_es("tennis", league, c["status"]) or "En juego", clock=None, period=None, situation=None, linescores=None, server=srv)
                desc = (st.get("description") or "")
                if st["state"] == "post" and desc.lower() in ("retired", "walkover", "default", "disqualified", "abandoned"):
                    out[-1]["wd"] = {"retired": "Retiro de un jugador (abandonó el partido)", "walkover": "Pasa por W.O. (un jugador no se presentó)", "default": "Descalificación",
                                     "disqualified": "Descalificación", "abandoned": "Partido abandonado"}[desc.lower()]
    out.sort(key=lambda g: g["date"])
    return out, ok

def _tennis_matches_for(evs, pid, limit=10):
    rows = []
    for e in evs:
        for gr in e.get("groupings", []):
            if "Singles" not in gr["grouping"]["displayName"]: continue
            for c in gr["competitions"]:
                if c["status"]["type"]["state"] != "post": continue
                cs = c.get("competitors", [])
                me = next((x for x in cs if str(x.get("id")) == pid), None)
                if not me: continue
                op = next((x for x in cs if x is not me), None)
                if not op or not op.get("athlete"): continue
                ms = [int(x["value"]) for x in me.get("linescores", []) if x.get("value") is not None]
                os_ = [int(x["value"]) for x in op.get("linescores", []) if x.get("value") is not None]
                rows.append(dict(date=c["date"], res="W" if me.get("winner") else "L", opp=op["athlete"].get("displayName"),
                                 score=" ".join(f"{a}-{b}" for a, b in zip(ms, os_)), tournament=e.get("name"), round=(c.get("round") or {}).get("displayName")))
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows[:limit]

async def tennis_detail(league, mid):
    games, ok = await tennis_games(league)
    g = next((x for x in games if x["id"] == mid), None)
    if not g:
        # puede ser un partido ya pasado: buscar sin filtro de fecha
        return None
    evs, _ = await tennis_events(league)
    rk = await tennis_rankings(league)
    A, B = g["home"], g["away"]
    fa, fb = _tennis_matches_for(evs, A["id"]), _tennis_matches_for(evs, B["id"])
    gaps = ["Cuotas (ESPN no publica momios de tenis): Sin dato", "Superficie / H2H / lesiones: Sin dato (no disponible en fuentes gratuitas)"]
    mk = await MK.game_market(league, g) if g["state"] == "pre" else None
    odds = MK.as_odds(mk, prefer=("sharp",)) if mk else None
    if odds:
        odds["src"] = "mk"
        gaps[0] = "Cuotas: sólo Pinnacle (referencia sharp, vía guest API pública); ESPN no publica momios de tenis. % tickets/% dinero: Sin dato"
    p_mkt = (odds.get("nv") or {}).get("ml", {}).get("home") if odds else None
    mdl = M.tennis_model(A["points"], B["points"], p_mkt_home=p_mkt)
    if mdl and mdl.get("imputed"):
        who = A["name"] if not A.get("points") else B["name"]
        gaps.append(f"Ranking de {who}: Sin dato → modelo con puntos imputados (muestra baja; se apoya en el mercado si hay ML)")
    res = dict(game=g, kind="tennis", odds=odds, gaps=gaps, form={"home": fa, "away": fb}, market=mk, odds_note=("Cuotas tomadas de Pinnacle (ESPN no publica tenis)." if odds else None))
    if g.get("live"): res["live"] = dict(g["live"], state=g["state"], stats=[], plays=[])
    if g["state"] == "pre": res["probs"] = PR.build(g, mdl, odds, mk, w=(M.blend_weight(mdl) if mdl else None))
    if mdl and g["state"] == "pre":
        cands = M.build_candidates(mdl, odds, A["name"], B["name"]) if odds else []
        conf = M.confidence(mdl, odds, {}, "tennis")
        M.apply_confidence(cands, conf)
        dec = M.decide(cands, mdl, A["name"], B["name"])
        if mk: MK.attach_signals(dec["candidates"], mk)
        lab = "Heurística por puntos de ranking (logística sobre ln de puntos)" + (" · ranking imputado" if mdl.get("imputed") else "")
        res["model"] = dict(kind="ranking", p_home=mdl["p_home"], p_away=mdl["p_away"], w_model=(M.blend_weight(mdl) if odds else None), label=lab, imputed=bool(mdl.get("imputed")))
        res["picks"] = dict(lean=dec["lean"], status=dec["status"], candidates=dec["candidates"], confidence=conf)
        if ST.ENABLED: ST.apply(res["picks"], {})
        res["pred"] = PRED.build(g, mdl, odds, "tennis", picks=res["picks"])
        if ST.ENABLED: ST.finalize(res["picks"], res["pred"])
    else:
        res["model"] = None
        res["picks"] = None
        if not mdl: gaps.append("Sin ranking de ninguno de los dos y sin ML de mercado → sin modelo")
        elif g["state"] != "pre": gaps.append(f"Juego en estado «{g['state']}»: el pick/predicción se calculan sólo antes del inicio")
    return res

# ------------------------------------------------------------------ MLB lanzadores (StatsAPI)
async def mlb_pitchers(home_name, away_name, iso):
    d0 = parse_dt(iso)
    if not d0: return None
    dates = {d0.astimezone(CDMX).strftime("%Y-%m-%d"), d0.strftime("%Y-%m-%d")}
    for ds in dates:
        sch = await get_json(f"{MLB_API}/schedule", ttl=300, params={"sportId": 1, "date": ds, "hydrate": "probablePitcher,team"})
        for dt in (sch or {}).get("dates", []):
            for g in dt["games"]:
                if g["teams"]["home"]["team"]["name"] == home_name and g["teams"]["away"]["team"]["name"] == away_name:
                    out = {"gamePk": g["gamePk"], "source": "MLB StatsAPI", "status": g["status"]["detailedState"]}
                    for side in ("home", "away"):
                        pp = g["teams"][side].get("probablePitcher")
                        if not pp: out[side] = None; continue
                        ppl = await get_json(f"{MLB_API}/people/{pp['id']}", ttl=900,
                                             params={"hydrate": f"stats(group=[pitching],type=[season,gameLog],season={d0.year})"})
                        p = (ppl or {}).get("people", [{}])[0]
                        season = next((s for s in p.get("stats", []) if s["type"]["displayName"] == "season"), None)
                        glog = next((s for s in p.get("stats", []) if s["type"]["displayName"] == "gameLog"), None)
                        st = season["splits"][0]["stat"] if season and season["splits"] else {}
                        last = []
                        if glog:
                            sp = sorted(glog["splits"], key=lambda x: x.get("date", ""))[-3:]
                            last = [dict(date=x.get("date"), summary=x["stat"].get("summary")) for x in reversed(sp)]
                        out[side] = dict(id=pp["id"], name=pp["fullName"], hand=(p.get("pitchHand") or {}).get("description"),
                                         era=st.get("era"), whip=st.get("whip"), ip=st.get("inningsPitched"), w=st.get("wins"), l=st.get("losses"),
                                         k=st.get("strikeOuts"), bb=st.get("baseOnBalls"), gs=st.get("gamesStarted"), last=last,
                                         confirmed=False)  # probable, no confirmado
                    return out
    return None


def _is_pass_yds_cat(cat):
    c = (cat or "").lower().replace("-", " ")
    return "passing" in c and "yard" in c

def _inj_confirmado(i):
    return classify_inj(i.get("status")) == "confirmado"

def nfl_qb_out(hid, aid, inj, lead):
    """Detecta QB titular (líder de pases) confirmado fuera. extra_margin se suma a mu = rh-ra+hfa:
    QB local fuera resta (perjudica al local); QB visita fuera suma. extra_total baja el total esperado.
    No trata 'Coach's Decision' ni questionable como baja del titular."""
    notes = []
    extra_margin = 0.0
    extra_total = 0.0
    sides = []
    for tid, side in ((hid, "home"), (aid, "away")):
        leaders = lead.get(tid) or lead.get(str(tid)) or []
        injuries = inj.get(tid) or inj.get(str(tid)) or []
        inj_by_id = {i.get("id"): i for i in injuries if i.get("id")}
        qb = None
        for l in leaders:
            if _is_pass_yds_cat(l.get("cat")):
                qb = l; break
        if not qb:
            # sin líder de pases publicado: no inventamos un titular
            sides.append(dict(side=side, tid=tid, qb=None, out=False, reason="Sin dato de líder de pases"))
            continue
        hit = inj_by_id.get(qb.get("id"))
        out = bool(hit and _inj_confirmado(hit))
        rec = dict(side=side, tid=tid, qb=qb.get("name"), qb_id=qb.get("id"), out=out,
                   status=(hit or {}).get("status") if hit else None)
        if out:
            notes.append(f"QB titular fuera: {qb.get('name')} ({hit.get('status')})")
            extra_total -= M.NFL_QB_OUT_TOTAL
            if side == "home":
                extra_margin -= M.NFL_QB_OUT_MARGIN
            else:
                extra_margin += M.NFL_QB_OUT_MARGIN
        sides.append(rec)
    return dict(extra_margin=extra_margin, extra_total=extra_total, notes=notes, sides=sides,
                applied=bool(notes))

def _era_adj(p):
    """Ajuste de margen (carreras) por abridor: ERA suavizada vs ~4.2 liga, ~5.5 IP, peso 0.6. Devuelve carreras ahorradas."""
    try:
        era = float(p["era"]); ip = float(p["ip"])
    except Exception: return 0.0
    lg = 4.2
    e = (era * ip + lg * 50) / (ip + 50)
    return max(-0.6, min(0.6, (lg - e) * 5.5 / 9 * 0.6))

# ------------------------------------------------------------------ detalle / análisis
INJ_OUT = ("out", "injured reserve", "suspension", "suspended", "inactive", "season-ending", "10-day il", "15-day il", "60-day il", "7-day il", "il")

def classify_inj(status):
    s = (status or "").lower()
    return "confirmado" if any(s.startswith(k) or k in s for k in INJ_OUT) and "day-to-day" not in s else "por_confirmar"

def _injuries(summ):
    out = {}
    for t in summ.get("injuries") or []:
        tid = str(t["team"]["id"]); lst = []
        for i in t.get("injuries", []):
            a = i.get("athlete", {}); det = i.get("details") or {}
            lst.append(dict(id=str(a.get("id")), name=a.get("displayName"), pos=(a.get("position") or {}).get("abbreviation"), status=i.get("status"),
                            kind=classify_inj(i.get("status")), detail=" · ".join(x for x in [det.get("type"), det.get("detail")] if x) or None,
                            ret=det.get("returnDate"), date=i.get("date")))
        out[tid] = lst
    return out

def _leaders(summ):
    out = {}
    for t in summ.get("leaders") or []:
        tid = str(t["team"]["id"]); lst = []
        for cat in t.get("leaders", [])[:8]:
            if not cat.get("leaders"): continue
            l = cat["leaders"][0]; a = l.get("athlete", {})
            lst.append(dict(cat=cat.get("displayName") or cat.get("name"), name=a.get("displayName"), id=str(a.get("id")), pos=(a.get("position") or {}).get("abbreviation"),
                            value=l.get("displayValue")))
        out[tid] = lst
    return out

def _h2h(summ):
    out = []
    for s in summ.get("seasonseries") or []:
        evs = []
        for e in s.get("events", []):
            if e.get("status") != "post": continue
            cs = e.get("competitors") or []
            h = next((c for c in cs if c.get("homeAway") == "home"), None); a = next((c for c in cs if c.get("homeAway") == "away"), None)
            if not h or not a: continue
            evs.append(dict(date=e.get("date"), home=h["team"].get("displayName"), away=a["team"].get("displayName"), hs=h.get("score"), as_=a.get("score"),
                            comp=e.get("competitionName") or e.get("roundName")))
        if evs: out.append(dict(title=s.get("title"), summary=s.get("summary") or s.get("shortSummary"), events=evs[:6]))
    return out

def _trends(league, fam, tsum, hid, aid, hname, aname, odds, injuries):
    t = []
    for tid, nm, is_home in ((hid, hname, True), (aid, aname, False)):
        s = tsum[tid]; o = s["overall"]
        if not o["n"]: t.append(f"{nm}: Sin dato de resultados."); continue
        if s["streak"]: t.append(f"{nm}: racha {s['streak']} · últimos 5: {s['last5']['text']} · últimos 10: {s['last10']['text']}")
        sp = s["home"] if is_home else s["away"]
        if sp["n"]:
            lab = "en casa" if is_home else "de visita"
            unit = "goles" if fam == "soccer" else ("carreras" if fam == "baseball" else "pts")
            t.append(f"{nm} {lab}: {sp['text']} ({sp['pf']:.1f} {unit} a favor / {sp['pa']:.1f} en contra por juego)")
        rows = s["recent"][:10]
        if fam == "soccer" and rows:
            btts = sum(1 for r in rows if r["pf"] > 0 and r["pa"] > 0); o25 = sum(1 for r in rows if r["pf"] + r["pa"] > 2.5)
            cs = sum(1 for r in rows if r["pa"] == 0)
            t.append(f"{nm}: ambos anotan {btts}/{len(rows)} · Over 2.5 {o25}/{len(rows)} · portería a cero {cs}/{len(rows)} (últimos {len(rows)} juegos)")
        elif rows:
            r5 = rows[:5]; avg = sum(r["pf"] + r["pa"] for r in r5) / len(r5)
            line = (odds or {}).get("total", {}).get("over", {}).get("line")
            extra = f" · línea actual {line:g}" if line else ""
            t.append(f"{nm}: promedio combinado de puntos/carreras últimos {len(r5)} juegos: {avg:.1f}{extra}")
    return t

async def analyze(league, eid):
    """Análisis del juego + registro automático de pick principal/sugerencias (sólo pre-juego) + picks ya registrados con su calificación."""
    out = await _analyze(league, eid)
    if out:
        try: PRED.attach(out)
        except Exception: out.pop("pred", None)
        try:
            REC.record_analysis(out)
            out["record"] = REC.game_rows(league, eid)
        except Exception:
            out["record"] = []
    return out

async def _analyze(league, eid):
    cfg = LEAGUES[league]; fam = cfg["family"]
    if fam == "tennis": return await tennis_detail(league, eid)
    summ = await get_json(f"{ESPN}/{cfg['path']}/summary", ttl=30, params={"event": eid})
    if not summ or not summ.get("header"): return None
    comp = summ["header"]["competitions"][0]
    hc = next(c for c in comp["competitors"] if c["homeAway"] == "home"); ac = next(c for c in comp["competitors"] if c["homeAway"] == "away")
    st = (comp.get("status") or {}).get("type") or summ["header"].get("status", {}).get("type", {}) or {}
    def side(c):
        t = c["team"]
        return dict(id=str(t["id"]), name=t.get("displayName"), short=t.get("shortDisplayName"), abbr=t.get("abbreviation"), logo=logo_of(t),
                    score=c.get("score"), record=_rec(c), winner=c.get("winner"), color=t.get("color"))
    H, A = side(hc), side(ac)
    gi = summ.get("gameInfo") or {}
    game = dict(id=eid, league=league, league_name=cfg["name"], sport=cfg["sport"], date=comp.get("date"), state=st.get("state", "pre"),
                status=LV.status_es(fam, league, comp.get("status")) if st.get("state") in ("in", "post") else (st.get("shortDetail") or st.get("description")), home=H, away=A, venue=(gi.get("venue") or {}).get("fullName"),
                neutral=bool(comp.get("neutralSite")), note=((comp.get("notes") or [{}])[0] or {}).get("headline"))
    wx = gi.get("weather")
    if wx and wx.get("temperature") is not None:
        game["weather"] = dict(temp_f=wx.get("temperature"), gust=wx.get("gust"), precip=wx.get("precipitation"))
    # ---- odds (sólo pre-juego; en vivo/final las cuotas ya no son pre-juego)
    odds = None
    if game["state"] == "pre":
        pc = (summ.get("pickcenter") or [None])[0] or (summ.get("odds") or [None])[0]
        odds = extract_odds(pc)
        if odds: odds["src"] = "espn"
    mk = None; odds_note = None
    if game["state"] == "pre":
        mk = await MK.game_market(league, game)
        if not odds and mk:
            odds = MK.as_odds(mk)
            if odds: odds["src"] = "mk"; odds_note = f"Cuotas tomadas de {odds['book']} (ESPN no publica línea para este juego)."
    R = await RT.get_ratings(league)
    gaps = []
    tsum = {H["id"]: RT.team_summary(R, H["id"]), A["id"]: RT.team_summary(R, A["id"])}
    inj = _injuries(summ); lead = _leaders(summ)
    if not inj: gaps.append("Lesiones: Sin dato (la fuente no las publica para esta liga/juego)")
    if not lead: gaps.append("Líderes/jugadores clave: Sin dato")
    if not odds and game["state"] == "pre": gaps.append("Cuotas: Sin dato (ni ESPN/DraftKings, ni Action Network, ni Pinnacle publican línea para este juego todavía)")
    if game["state"] == "pre" and mk and not mk.get("splits"): gaps.append("% tickets / % dinero: Sin dato (Action Network no tiene este juego, o no lo cubre: Liga MX y tenis no están cubiertos)")
    if game["state"] == "pre" and not mk: gaps.append("Comparador multi-casa: Sin dato (ninguna fuente de mercado tiene este juego)")
    # ---- MLB lanzadores / NFL QB titular fuera
    pitchers = None; extra = 0.0; extra_total = 0.0; qb_out = None
    if league == "mlb":
        pitchers = await mlb_pitchers(H["name"], A["name"], game["date"])
        if not pitchers: gaps.append("Abridores probables: Sin dato")
        else:
            if pitchers.get("home") and pitchers.get("away"):
                extra = _era_adj(pitchers["home"]) - _era_adj(pitchers["away"])
            else: gaps.append("Abridor probable de uno de los equipos: Sin dato (no anunciado)")
    elif league == "nfl":
        qb_out = nfl_qb_out(H["id"], A["id"], inj, lead)
        extra = qb_out["extra_margin"]
        extra_total = qb_out["extra_total"]
        if qb_out["applied"]:
            gaps.append("Ajuste QB titular fuera: " + "; ".join(qb_out["notes"]))
        elif any(s.get("reason") == "Sin dato de líder de pases" for s in qb_out["sides"]):
            gaps.append("Líder de pases (QB titular): Sin dato en uno o ambos equipos; no se aplicó ajuste de QB fuera")
    # ---- modelo
    mdl = None
    if fam == "soccer": mdl = M.soccer_model(R, H["id"], A["id"], game["neutral"])
    else: mdl = M.margin_model(R, H["id"], A["id"], game["neutral"], extra_margin=extra, extra_total=extra_total)
    out = dict(game=game, kind="team", odds=odds, teams={H["id"]: tsum[H["id"]], A["id"]: tsum[A["id"]]}, injuries=inj, leaders=lead,
               h2h=_h2h(summ), gaps=gaps, pitchers=pitchers, ratings_n=R["n_games"],
               espn_predictor=(summ.get("predictor") and dict(home=summ["predictor"]["homeTeam"].get("gameProjection"), away=summ["predictor"]["awayTeam"].get("gameProjection"))),
               ats=_ats(summ))
    out["market"] = mk; out["odds_note"] = odds_note
    out["trends"] = _trends(league, fam, tsum, H["id"], A["id"], H["name"], A["name"], odds, inj)
    if not mdl:
        out["model"] = None; out["picks"] = None
        gaps.append("Modelo: Sin dato suficiente de resultados de uno de los equipos")
        if game["state"] == "pre": out["probs"] = PR.build(game, None, odds, mk)
        return out
    # lesionados clave (líderes de equipo en lista)
    key = False; key_names = []
    for tid in (H["id"], A["id"]):
        ids = {l["id"]: l for l in lead.get(tid, [])}
        for i in inj.get(tid, []):
            if i["id"] in ids and i["status"] and i["status"].lower() not in ("probable",):
                key = True; key_names.append(f"{i['name']} ({i['status']})")
    flags = dict(key_injury=key, pitchers_known=bool(pitchers and pitchers.get("home") and pitchers.get("away")))
    mout = dict(kind=mdl["kind"], p_home=mdl["p_home"], p_draw=mdl.get("p_draw"), p_away=mdl["p_away"], exp_total=mdl.get("exp_total"), exp_margin=mdl.get("mu"),
                sample=mdl["sample"], n_home=mdl["n_home"], n_away=mdl["n_away"], w_model=M.blend_weight(mdl), hfa=mdl.get("hfa"),
                lam_home=mdl.get("lam_home"), lam_away=mdl.get("lam_away"), pitcher_adj=extra if league == "mlb" else None,
                qb_adj=extra if league == "nfl" else None, qb_total_adj=extra_total if league == "nfl" else None,
                qb_out=qb_out,
                rating_home=mdl.get("rating_home"), rating_away=mdl.get("rating_away"), top_scores=mdl.get("mat_top"), key_injuries=key_names)
    out["model"] = mout
    if game["state"] == "pre":
        cor = None
        if fam == "soccer":
            try: cor = await PRED.corners_info(league, cfg["path"], tsum[H["id"]], tsum[A["id"]], H["id"], A["id"])
            except Exception: cor = None
        out["_cor"] = cor
    if game["state"] == "pre" and fam == "soccer" and odds:
        from . import props as PROPS
        from .odds import am_to_prob, devig
        bt = await PROPS.btts_odds(league, game["id"])
        if bt:
            odds["btts"] = dict(yes=bt["yes"], no=bt["no"]); odds["btts_open"] = dict(yes=bt.get("open_yes"), no=bt.get("open_no"))
            nvb, _ = devig([am_to_prob(bt["yes"]), am_to_prob(bt["no"])])
            odds.setdefault("nv", {})["btts"] = dict(yes=nvb[0], no=nvb[1])
    if game["state"] == "pre":
        cands = M.build_candidates(mdl, odds, H["name"], A["name"])
        dec = M.decide(cands, mdl, H["name"], A["name"])
        conf = M.confidence(mdl, odds, flags, fam)
        M.apply_confidence(cands, conf)
        dec = M.decide(cands, mdl, H["name"], A["name"])
        if mk: MK.attach_signals(dec["candidates"], mk)
        out["picks"] = dict(lean=dec["lean"], status=dec["status"], candidates=dec["candidates"], confidence=conf)
        wx = game.get("weather") or {}
        crit = "abridor de MLB sin confirmar" if league == "mlb" and not flags["pitchers_known"] else None
        if ST.ENABLED: ST.apply(out["picks"], dict(key_injury=flags["key_injury"], critical_missing=crit, windy=(wx.get("gust") or 0) >= 25))
        out["pred"] = PRED.build(game, mdl, odds, fam, out.pop("_cor", None), picks=out["picks"])
        if ST.ENABLED: ST.finalize(out["picks"], out["pred"])
        out["probs"] = PR.build(game, mdl, odds, mk)
    else:
        out["picks"] = None
        gaps.append("Picks no disponibles: el juego ya empezó o terminó (las cuotas ya no son pre-juego)")
    return out

def _ats(summ):
    out = []
    for t in summ.get("againstTheSpread") or []:
        recs = t.get("records") or []
        if recs: out.append(dict(team=t["team"].get("displayName"), records=[{k: r.get(k) for k in ("type", "summary", "displayValue")} for r in recs]))
    return out

# ------------------------------------------------------------------ picks del día
_picks_cache = {}

from . import strict as ST

def _pred_brief(p):
    if not p: return None
    return dict(winner=p.get("winner"), score=p.get("score"), total=p.get("total"), spread=p.get("spread"), btts=p.get("btts"))

async def picks(scope="24h"):
    key = scope
    ent = _picks_cache.get(key)
    if ent and time.time() - ent[0] < 120: return ent[1]
    now = datetime.now(timezone.utc); nowl = now_cdmx()
    if scope == "hoy": t0, t1 = now, nowl.replace(hour=23, minute=59, second=59).astimezone(timezone.utc)
    elif scope == "manana":
        d = (nowl + timedelta(days=1)); t0 = d.replace(hour=0, minute=0, second=0).astimezone(timezone.utc); t1 = d.replace(hour=23, minute=59, second=59).astimezone(timezone.utc)
    elif scope == "72h": t0, t1 = now, now + timedelta(hours=72)
    else: t0, t1 = now, now + timedelta(hours=24)
    leagues = list(LEAGUES.keys())
    lists = await asyncio.gather(*[list_games(l) for l in leagues])
    games = []
    for l, (gs, ok) in zip(leagues, lists):
        for g in gs:
            d = parse_dt(g["date"])
            if g["state"] == "pre" and d and t0 <= d <= t1: games.append(g)
    async def one(g):
        try:
            a = await analyze(g["league"], g["id"])
        except Exception as ex:
            return None
        if not a or not a.get("picks"): return None
        p = a["picks"]
        return dict(game=a["game"], lean=p["lean"], status=p["status"], confidence=p["confidence"], has_odds=bool(a.get("odds")),
                    official=p.get("official") or [], considered=p.get("considered") or [], strict=("official" in p), pred=_pred_brief(a.get("pred")),
                    top=[c for c in p["candidates"][:3]], model=a.get("model"), brief=PR.brief(a.get("probs")))
    rs = [r for r in await asyncio.gather(*[one(g) for g in games]) if r]
    pri = {"PICK": 0, "LEAN": 1, "REVISAR": 2, "PASS": 3, "SIN_LINEA": 4}
    if ST.ENABLED: rs.sort(key=lambda r: (pri.get(r["status"], 3), -(((r["lean"] or {}).get("score")) or 0)))
    else:
        cw = {"Alta": 2, "Media": 1, "Baja": 0}
        def _pr(r):
            lean = r.get("lean") or {}
            ev = lean.get("ev") if lean.get("ev") is not None else -999
            conf = (r.get("confidence") or {}).get("level")
            div = 1 if lean.get("divergence_high") else 0
            return (pri.get(r["status"], 3), div, -ev, -cw.get(conf, 0))
        rs.sort(key=_pr)
    res = dict(scope=scope, generated=time.time(), n_games=len(games), items=rs, window=[t0.isoformat(), t1.isoformat()])
    _picks_cache[key] = (time.time(), res)
    return res
