"""Mercado multi-casa: comparador de cuotas, consenso sin vig, movimiento de línea, % tickets/% dinero y señales (RLM / dinero inteligente).
Fuentes gratuitas SIN llave de usuario:
  · Action Network (api.actionnetwork.com, endpoint público 'publicbetting'): DraftKings, FanDuel, BetMGM, Caesars, BetRivers, bet365,
    Fanatics, Unibet + 'Consenso' + 'Apertura' + % de tickets y % de dinero (NBA, NFL, NHL, MLB y fútbol europeo/Champions; sin Liga MX ni tenis).
  · Pinnacle (guest API pública, referencia 'sharp'): NBA, NFL, NHL, MLB, fútbol (incl. Liga MX) y tenis. No trae % de apuestas.
Si algo no existe se devuelve None y la UI muestra 'Sin dato'. Nunca se inventan cifras."""
import asyncio, os, re, time, unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .cache import get_json, fetched_at
from .odds import am_to_prob, am_to_dec, devig, fmt_am, prob_to_am
from . import history

ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Accept": "application/json"}

# ---------------------------------------------------------------- Action Network
AN_URL = "https://api.actionnetwork.com/web/v2/scoreboard/publicbetting/{slug}"
AN_BOOKS = {15: ("Consenso AN", "consensus"), 30: ("Apertura AN", "open"), 68: ("DraftKings", "book"), 69: ("FanDuel", "book"), 75: ("BetMGM", "book"),
            123: ("Caesars", "book"), 71: ("BetRivers", "book"), 79: ("bet365", "book"), 2988: ("Fanatics", "book"), 247: ("Unibet", "book")}
AN_SLUG = {"mlb": "mlb", "nfl": "nfl", "nba": "nba", "nhl": "nhl", "eng.1": "soccer", "esp.1": "soccer", "ita.1": "soccer", "ger.1": "soccer", "uefa.champions": "soccer"}
SPLIT_ORDER = [15, 68, 69, 75, 123, 71, 79, 2988, 247]

# ---------------------------------------------------------------- Pinnacle (guest API pública)
PIN_ON = os.environ.get("PINNACLE", "1") != "0"
PIN_URL = "https://guest.api.arcadia.pinnacle.com/0.1"
PIN_KEY = os.environ.get("PINNACLE_GUEST_KEY", "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R")   # llave 'guest' pública del sitio web (sin cuenta); configurable/desactivable
PIN_SPORT = {"nba": 4, "nfl": 15, "nhl": 19, "mlb": 3, "mex.1": 29, "eng.1": 29, "esp.1": 29, "ita.1": 29, "ger.1": 29, "uefa.champions": 29, "atp": 33, "wta": 33}
PIN_NAME = {"nba": "NBA", "nfl": "NFL", "nhl": "NHL", "mlb": "MLB", "mex.1": "Mexico - Liga MX", "eng.1": "England - Premier League", "esp.1": "Spain - La Liga",
            "ita.1": "Italy - Serie A", "ger.1": "Germany - Bundesliga", "uefa.champions": "UEFA - Champions League"}

THR_MAJ2, THR_MAJ3, THR_MOVE_PP, THR_SHARP = 55, 45, 1.5, 10

# ---------------------------------------------------------------- nombres
WEAK = {"new", "york", "los", "angeles", "san", "city", "united", "real", "de", "la", "st", "fc", "cf", "sc", "ac", "as", "afc", "club", "the", "calcio", "sv", "fk", "cd",
        "ud", "rc", "and", "of", "al", "1913", "1899", "1909", "1904", "1893", "hockey", "athletic", "sporting", "deportivo", "atletico", "inter", "borussia", "olympique"}
ALIAS = {"internazionale": "inter", "utd": "united", "spurs": "tottenham", "wolves": "wolverhampton", "psg": "paris", "munchen": "munich", "koln": "cologne",
         "gladbach": "monchengladbach", "mgladbach": "monchengladbach", "nott": "nottingham", "bilbao": "athletic", "hamburger": "hamburg", "milan": "milan"}

def _toks(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return {ALIAS.get(t, t) for t in re.findall(r"[a-z0-9]+", s)}

def _sim(a, b):
    ta, tb = _toks(a), _toks(b)
    strong = (ta & tb) - WEAK
    if not strong:
        both = ta & tb
        if not both: return 0
        if ta <= tb or tb <= ta: return 0.9 + len(both) / len(ta | tb) * 0.1   # un nombre contenido en el otro ('Deportivo' / 'Deportivo de A Coruña')
        return 0
    return 1 + len(ta & tb) / len(ta | tb)

def match_event(events, hname, aname, start, tol_h=3.0):
    best = None
    for ev in events:
        if start and ev.get("start") and abs((ev["start"] - start).total_seconds()) > tol_h * 3600: continue
        a1, a2 = _sim(ev["home"], hname), _sim(ev["away"], aname)
        b1, b2 = _sim(ev["home"], aname), _sim(ev["away"], hname)
        s_dir = (a1 + a2) if (a1 > 0 and a2 > 0) else 0
        s_rev = (b1 + b2) if (b1 > 0 and b2 > 0) else 0
        if max(s_dir, s_rev) <= 0: continue
        sc, flip = (s_dir, False) if s_dir >= s_rev else (s_rev, True)
        if not best or sc > best[0]: best = (sc, ev, flip)
    return (best[1], best[2]) if best else (None, False)

def _flip_book(b):
    if not b: return b
    n = dict(b)
    if b.get("ml"): n["ml"] = {("away" if k == "home" else "home" if k == "away" else k): v for k, v in b["ml"].items()}
    if b.get("spread"): n["spread"] = {("away" if k == "home" else "home"): v for k, v in b["spread"].items()}
    return n

def _flip_splits(sp):
    out = {}
    for mk, d in (sp or {}).items():
        out[mk] = {("away" if k == "home" else "home" if k == "away" else k): v for k, v in d.items()} if mk in ("ml", "spread") else dict(d)
    return out

def _dt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception: return None

# ---------------------------------------------------------------- Action Network: parseo
def _an_book(bid, markets, with_pct=False):
    ev = (markets.get(str(bid)) or {}).get("event") or {}
    ml, sp, tt = {}, {}, {}
    pct = {"ml": {}, "spread": {}, "total": {}}
    def pc(o):
        bi = o.get("bet_info") or {}
        t = (bi.get("tickets") or {}).get("percent"); m = (bi.get("money") or {}).get("percent")
        return (t, m) if (t or m) else None
    for o in ev.get("moneyline", []) or []:
        if o.get("is_live"): continue
        s = o.get("side"); od = o.get("odds")
        if s in ("home", "away", "draw") and od not in (None, 0) and s not in ml:
            ml[s] = int(od)
            p = pc(o)
            if p: pct["ml"][s] = dict(t=p[0], m=p[1])
    for o in ev.get("spread", []) or []:
        if o.get("is_live"): continue
        s = o.get("side"); od = o.get("odds"); v = o.get("value")
        if s in ("home", "away") and od not in (None, 0) and v is not None and s not in sp:
            sp[s] = dict(line=float(v), price=int(od))
            p = pc(o)
            if p: pct["spread"][s] = dict(t=p[0], m=p[1])
    for o in ev.get("total", []) or []:
        if o.get("is_live"): continue
        s = o.get("side"); od = o.get("odds"); v = o.get("value")
        if s in ("over", "under") and od not in (None, 0) and v is not None and s not in tt:
            tt[s] = dict(line=float(v), price=int(od))
            p = pc(o)
            if p: pct["total"][s] = dict(t=p[0], m=p[1])
    if len(sp) == 2 and abs(sp["home"]["line"] + sp["away"]["line"]) > 1e-9: sp = {}
    if len(tt) == 2 and tt["over"]["line"] != tt["under"]["line"]: tt = {}
    if not (ml or sp or tt): return None, pct
    nm, kind = AN_BOOKS[bid]
    return dict(id=f"an{bid}", name=nm, kind=kind, ml=ml, spread=sp, total=tt), pct

async def an_events(slug, d, week=None):
    params = {"bookIds": ",".join(str(b) for b in AN_BOOKS), "date": d.strftime("%Y%m%d")}
    if week: params["week"] = week
    url = AN_URL.format(slug=slug)
    data = await get_json(url, ttl=240, params=params, headers=UA)
    if not data: return [], None
    ts = fetched_at(url, params)
    out = []
    for g in data.get("games", []):
        teams = {t["id"]: t for t in g.get("teams", [])}
        h, a = teams.get(g.get("home_team_id")), teams.get(g.get("away_team_id"))
        if not h or not a or g.get("status") not in ("scheduled", "created", None): continue
        mk = g.get("markets") or {}
        books = []; splits = {"ml": {}, "spread": {}, "total": {}}
        for bid in AN_BOOKS:
            b, pct = _an_book(bid, mk)
            if b: books.append(b)
            if bid in SPLIT_ORDER:
                for m in splits:
                    for s, v in pct[m].items():
                        if s not in splits[m]: splits[m][s] = v
        out.append(dict(src="an", id=g["id"], home=h["full_name"], away=a["full_name"], start=_dt(g.get("start_time")), books=books, splits=splits,
                        league_name=g.get("league_name"), ts=ts, week=g.get("week")))
    return out, ts

# ---------------------------------------------------------------- Pinnacle: parseo
def _pin_entry(markets):
    """markets: lista de mercados straight de un matchup. Toma periodo 0, línea principal (no alterna)."""
    ml, sp, tt = {}, {}, {}
    cand_sp, cand_tt = [], []
    for q in markets:
        if q.get("period") != 0 or q.get("status") != "open" or q.get("isAlternate"): continue
        pr = {p["designation"]: p for p in q.get("prices", []) if "designation" in p and p.get("price") not in (None, 0)}
        if q["type"] == "moneyline":
            for s in ("home", "away", "draw"):
                if s in pr: ml[s] = int(pr[s]["price"])
        elif q["type"] == "spread" and "home" in pr and "away" in pr and "points" in pr["home"]:
            cand_sp.append({"home": dict(line=float(pr["home"]["points"]), price=int(pr["home"]["price"])), "away": dict(line=float(pr["away"]["points"]), price=int(pr["away"]["price"]))})
        elif q["type"] == "total" and "over" in pr and "under" in pr and "points" in pr["over"]:
            cand_tt.append({"over": dict(line=float(pr["over"]["points"]), price=int(pr["over"]["price"])), "under": dict(line=float(pr["under"]["points"]), price=int(pr["under"]["price"]))})
    bal = lambda c, k: abs(am_to_prob(c[k[0]]["price"]) - am_to_prob(c[k[1]]["price"]))
    if cand_sp: sp = min(cand_sp, key=lambda c: bal(c, ("home", "away")))
    if cand_tt: tt = min(cand_tt, key=lambda c: bal(c, ("over", "under")))
    if not (ml or sp or tt): return None
    return dict(id="pin", name="Pinnacle", kind="sharp", ml=ml, spread=sp, total=tt)

async def _pin_get(path, ttl):
    return await get_json(PIN_URL + path, ttl=ttl, headers={"x-api-key": PIN_KEY, "Accept": "application/json", "User-Agent": UA["User-Agent"]})

async def pin_events(league):
    if not PIN_ON: return [], None
    sid = PIN_SPORT.get(league)
    if not sid: return [], None
    lids = []
    if sid == 33:
        ms = await _pin_get(f"/sports/{sid}/matchups", 300) or []
        seen = {}
        for x in ms:
            lg = x.get("league") or {}; nm = lg.get("name") or ""
            if x.get("type") == "matchup" and not x.get("parentId") and re.search(rf"\b{league.upper()}\b", nm) and "Doubles" not in nm:
                seen[lg["id"]] = nm
        lids = list(seen)[:30]
    else:
        ls = await _pin_get(f"/sports/{sid}/leagues?all=false", 3600) or []
        want = PIN_NAME.get(league)
        lids = [l["id"] for l in ls if l.get("name") == want][:1]
    if not lids: return [], None
    async def one(lid):
        m, k = await asyncio.gather(_pin_get(f"/leagues/{lid}/matchups", 240), _pin_get(f"/leagues/{lid}/markets/straight", 240))
        return m or [], k or []
    res = await asyncio.gather(*[one(l) for l in lids])
    out = []; ts = None
    for lid, (ms, ks) in zip(lids, res):
        t = fetched_at(f"{PIN_URL}/leagues/{lid}/markets/straight"); ts = max(ts or 0, t or 0) or ts
        by = {}
        for q in ks: by.setdefault(q["matchupId"], []).append(q)
        for x in ms:
            if x.get("type") != "matchup" or x.get("parentId") or x.get("status") not in ("pending", "started"): continue
            ps = {p.get("alignment"): p.get("name") for p in x.get("participants", [])}
            if "home" not in ps or "away" not in ps: continue
            b = _pin_entry(by.get(x["id"], []))
            if b: out.append(dict(src="pin", id=x["id"], home=ps["home"], away=ps["away"], start=_dt(x.get("startTime")), books=[b], splits={}, ts=t))
    return out, ts

# ---------------------------------------------------------------- utilidades de mercado
def nv_of(b):
    """Probabilidades sin vig por mercado para una casa (normalización proporcional)."""
    out = {}
    ml = b.get("ml") or {}
    sides = [s for s in ("home", "draw", "away") if s in ml]
    if len(sides) >= 2:
        ps, ov = devig([am_to_prob(ml[s]) for s in sides]); out["ml"] = dict(zip(sides, ps)); out["ml_vig"] = ov
    sp = b.get("spread") or {}
    if "home" in sp and "away" in sp:
        ps, ov = devig([am_to_prob(sp["home"]["price"]), am_to_prob(sp["away"]["price"])]); out["spread"] = dict(home=ps[0], away=ps[1], line=sp["home"]["line"]); out["spread_vig"] = ov
    tt = b.get("total") or {}
    if "over" in tt and "under" in tt:
        ps, ov = devig([am_to_prob(tt["over"]["price"]), am_to_prob(tt["under"]["price"])]); out["total"] = dict(over=ps[0], under=ps[1], line=tt["over"]["line"]); out["total_vig"] = ov
    return out

def as_odds(mk, prefer=("consensus", "sharp")):
    """Estructura tipo ESPN (para el modelo) a partir de consenso/Pinnacle cuando ESPN no trae línea."""
    if not mk: return None
    for kind in prefer:
        b = next((x for x in mk["books"] if x["kind"] == kind and x.get("ml")), None)
        if b:
            o = dict(book=("Pinnacle" if kind == "sharp" else "Consenso Action Network"), ml=dict(b["ml"]), spread=dict(b.get("spread") or {}), total=dict(b.get("total") or {}), open={})
            nv = nv_of(b)
            o["nv"] = {k: v for k, v in nv.items() if k in ("ml", "ml_vig", "spread_vig", "total_vig") or k in ("spread", "total") and True}
            if "spread" in nv: o["nv"]["spread"] = dict(home=nv["spread"]["home"], away=nv["spread"]["away"])
            if "total" in nv: o["nv"]["total"] = dict(over=nv["total"]["over"], under=nv["total"]["under"])
            return o
    return None

def _ref_line(books, mkt, side, cons):
    if cons and (cons.get(mkt) or {}).get(side): return cons[mkt][side]["line"]
    ls = [b[mkt][side]["line"] for b in books if b["kind"] in ("book", "sharp") and (b.get(mkt) or {}).get(side)]
    return max(set(ls), key=ls.count) if ls else None

def _flags(books, cons):
    """Marca mejor precio (misma línea que el consenso) y mejor línea (número más favorable)."""
    fl = {b["id"]: {} for b in books}
    real = [b for b in books if b["kind"] == "book"]
    for s in ("home", "away", "draw"):
        v = [(b["ml"][s], b["id"]) for b in real if s in (b.get("ml") or {})]
        if v:
            mx = max(p for p, _ in v)
            for p, i in v:
                if p == mx and len(v) > 1: fl[i][f"ml.{s}"] = "best"
    for mkt, sides, better in (("spread", ("home", "away"), lambda a, b: a > b), ("total", ("over", "under"), None)):
        for s in sides:
            ref = _ref_line(books, mkt, s, cons)
            if ref is None: continue
            if mkt == "spread": better = lambda a, b: a > b
            else: better = (lambda a, b: a < b) if s == "over" else (lambda a, b: a > b)
            cells = [(b[mkt][s], b["id"]) for b in real if (b.get(mkt) or {}).get(s)]
            same = [(c["price"], i) for c, i in cells if c["line"] == ref]
            if len(same) > 1:
                mx = max(p for p, _ in same)
                for p, i in same:
                    if p == mx: fl[i][f"{mkt}.{s}"] = "best"
            bl = [(c, i) for c, i in cells if better(c["line"], ref)]
            if bl:
                top = bl[0][0]["line"]
                for c, i in bl:
                    if better(c["line"], top): top = c["line"]
                tops = [(c["price"], i) for c, i in bl if c["line"] == top]
                mx = max(p for p, _ in tops)
                for p, i in tops:
                    if p == mx: fl[i][f"{mkt}.{s}"] = "line"
    return fl

def _consensus_nv(books, cons):
    real = [b for b in books if b["kind"] == "book"]
    out = {}
    acc = {"ml": {}, "spread": {}, "total": {}}; cnt = {"ml": 0, "spread": 0, "total": 0}
    ref_sp = _ref_line(books, "spread", "home", cons); ref_tt = _ref_line(books, "total", "over", cons)
    for b in real:
        nv = nv_of(b)
        if "ml" in nv and len(nv["ml"]) == len(((cons or {}).get("ml") or nv["ml"])):
            for s, p in nv["ml"].items(): acc["ml"][s] = acc["ml"].get(s, 0) + p
            cnt["ml"] += 1
        if "spread" in nv and nv["spread"]["line"] == ref_sp:
            for s in ("home", "away"): acc["spread"][s] = acc["spread"].get(s, 0) + nv["spread"][s]
            cnt["spread"] += 1
        if "total" in nv and nv["total"]["line"] == ref_tt:
            for s in ("over", "under"): acc["total"][s] = acc["total"].get(s, 0) + nv["total"][s]
            cnt["total"] += 1
    for m in acc:
        if cnt[m]:
            out[m] = {s: v / cnt[m] for s, v in acc[m].items()}; out[m]["n"] = cnt[m]
            if m == "spread": out[m]["line"] = ref_sp
            if m == "total": out[m]["line"] = ref_tt
    return out

# ---------------------------------------------------------------- movimiento, % y señales
def _movement(openb, cur):
    if not openb or not cur: return None
    mv = {}
    no, nc = nv_of(openb), nv_of(cur)
    if openb.get("ml") and cur.get("ml"):
        d = {}
        for s in cur["ml"]:
            if s in openb["ml"]:
                d[s] = dict(open=openb["ml"][s], cur=cur["ml"][s], open_nv=(no.get("ml") or {}).get(s), cur_nv=(nc.get("ml") or {}).get(s),
                            d_nv_pp=((nc["ml"][s] - no["ml"][s]) * 100 if no.get("ml") and nc.get("ml") and s in no["ml"] and s in nc["ml"] else None))
        mv["ml"] = d
    if openb.get("spread") and cur.get("spread") and "home" in openb["spread"] and "home" in cur["spread"]:
        o, c = openb["spread"], cur["spread"]
        mv["spread"] = dict(open_line=o["home"]["line"], cur_line=c["home"]["line"], d_line_home=c["home"]["line"] - o["home"]["line"],
                            open_price=dict(home=o["home"]["price"], away=o["away"]["price"]), cur_price=dict(home=c["home"]["price"], away=c["away"]["price"]),
                            d_nv_home_pp=((nc["spread"]["home"] - no["spread"]["home"]) * 100 if no.get("spread") and nc.get("spread") else None))
    if openb.get("total") and cur.get("total") and "over" in openb["total"] and "over" in cur["total"]:
        o, c = openb["total"], cur["total"]
        mv["total"] = dict(open_line=o["over"]["line"], cur_line=c["over"]["line"], d_line=c["over"]["line"] - o["over"]["line"],
                           open_price=dict(over=o["over"]["price"], under=o["under"]["price"]), cur_price=dict(over=c["over"]["price"], under=c["under"]["price"]),
                           d_nv_over_pp=((nc["total"]["over"] - no["total"]["over"]) * 100 if no.get("total") and nc.get("total") else None))
    return mv or None

OPP = {"home": "away", "away": "home", "over": "under", "under": "over"}

def _signals(splits, mv, cur):
    """Indicadores por mercado. RLM = línea/precio se mueve CONTRA el lado con mayoría de tickets. Dinero inteligente = %dinero >> %tickets."""
    sig = {}
    for mkt, sides in (("ml", ("home", "away", "draw")), ("spread", ("home", "away")), ("total", ("over", "under"))):
        sp = (splits or {}).get(mkt) or {}
        t = {s: sp[s].get("t") for s in sides if s in sp and sp[s].get("t") is not None}
        m = {s: sp[s].get("m") for s in sides if s in sp and sp[s].get("m") is not None}
        if not t:
            sig[mkt] = None; continue
        three = (mkt == "ml" and "draw" in t)
        cand_sides = [s for s in t if s != "draw"]
        pub = max(cand_sides, key=lambda s: t[s]) if cand_sides else None
        thr = THR_MAJ3 if three else THR_MAJ2
        public = pub if pub and t[pub] >= thr else None
        d = dict(tickets=t, money=m, public_side=public, rlm=False, rlm_side=None, move_dir=None, move_text=None, sharp_side=None, sharp_diff=None)
        # movimiento respecto al lado público
        mm = (mv or {}).get(mkt)
        if public and mm:
            if mkt == "ml":
                dpp = (mm.get(public) or {}).get("d_nv_pp")
                if dpp is not None:
                    d["move_text"] = f"prob. s/vig del lado público {dpp:+.1f} pp (apertura → actual)"
                    d["move_dir"] = "contra" if dpp <= -THR_MOVE_PP else ("con" if dpp >= THR_MOVE_PP else "sin")
                    if d["move_dir"] == "contra":
                        others = [s for s in mm if s not in (public, "draw") or (three and s != public)]
                        best = max((s for s in mm if s != public), key=lambda s: (mm[s].get("d_nv_pp") or -99), default=None)
                        d["rlm_side"] = best
            elif mkt == "spread":
                dl = mm["d_line_home"] if public == "home" else -mm["d_line_home"]   # >0: el lado público ahora "cuesta menos"
                if abs(dl) >= 0.25:
                    d["move_dir"] = "contra" if dl > 0 else "con"
                    d["move_text"] = f"línea {mm['open_line']:+g} → {mm['cur_line']:+g} (local); el lado público {'cuesta menos' if dl > 0 else 'cuesta más'}"
                elif mm.get("d_nv_home_pp") is not None:
                    dpp = mm["d_nv_home_pp"] if public == "home" else -mm["d_nv_home_pp"]
                    d["move_text"] = f"misma línea; precio s/vig del lado público {dpp:+.1f} pp"
                    d["move_dir"] = "contra" if dpp <= -THR_MOVE_PP else ("con" if dpp >= THR_MOVE_PP else "sin")
                if d["move_dir"] == "contra": d["rlm_side"] = OPP[public]
            elif mkt == "total":
                dl = mm["d_line"] if public == "over" else -mm["d_line"]   # >0: línea sube hacia el lado público (con el público)
                if abs(dl) >= 0.25:
                    d["move_dir"] = "con" if dl > 0 else "contra"
                    d["move_text"] = f"total {mm['open_line']:g} → {mm['cur_line']:g}"
                elif mm.get("d_nv_over_pp") is not None:
                    dpp = mm["d_nv_over_pp"] if public == "over" else -mm["d_nv_over_pp"]
                    d["move_text"] = f"mismo total; precio s/vig del lado público {dpp:+.1f} pp"
                    d["move_dir"] = "contra" if dpp <= -THR_MOVE_PP else ("con" if dpp >= THR_MOVE_PP else "sin")
                if d["move_dir"] == "contra": d["rlm_side"] = OPP[public]
            d["rlm"] = bool(d["move_dir"] == "contra" and d["rlm_side"])
        # dinero vs tickets
        if m:
            diffs = {s: m[s] - t[s] for s in m if s in t and s != "draw" or (s in t and s == "draw")}
            if diffs:
                s = max(diffs, key=lambda k: diffs[k])
                if diffs[s] >= THR_SHARP: d["sharp_side"] = s; d["sharp_diff"] = diffs[s]
        sig[mkt] = d
    return sig

async def _lookup(league, game):
    start = _dt(game.get("date"))
    hn, an_ = game["home"]["name"], game["away"]["name"]
    tasks = []
    async def an_part():
        slug = AN_SLUG.get(league)
        if not slug or not start: return None, None, False
        d0 = start.astimezone(ET).date()
        for d in (d0, d0 - timedelta(days=1), d0 + timedelta(days=1)):
            evs, ts = await an_events(slug, d)
            ev, flip = match_event(evs, hn, an_, start)
            if ev: return ev, ts, flip
            if slug == "nfl" and d == d0 and evs:      # NFL: Action Network publica por semana; probar semanas siguientes
                wk = max([e.get("week") or 0 for e in evs] or [0])
                for w in range(wk, wk + 3):
                    if not w: continue
                    evs2, ts2 = await an_events(slug, d, week=w)
                    ev, flip = match_event(evs2, hn, an_, start)
                    if ev: return ev, ts2, flip
        return None, None, False
    async def pin_part():
        evs, ts = await pin_events(league)
        ev, flip = match_event(evs, hn, an_, start, tol_h=(30 if league in ("atp", "wta") else 3.0))
        return ev, ts, flip
    (a, ats, af), (p, pts, pf) = await asyncio.gather(an_part(), pin_part())
    return (a, ats, af), (p, pts, pf)

_mcache = {}

async def game_market(league, game, snapshot=True):
    """Devuelve el bloque de mercado del juego (o None si ninguna fuente tiene el juego)."""
    key = (league, game["id"])
    ent = _mcache.get(key)
    if ent and time.time() - ent[0] < 90: return ent[1]
    try:
        (a, ats, af), (p, pts, pf) = await asyncio.wait_for(_lookup(league, game), 25)
    except Exception:
        return ent[1] if ent else None
    books, srcs = [], []
    splits = {}
    if a:
        bk = [(_flip_book(b) if af else b) for b in a["books"]]
        books += bk; splits = _flip_splits(a["splits"]) if af else a["splits"]
        srcs.append(dict(name="Action Network", n_books=len([b for b in bk if b["kind"] == "book"]), ts=ats))
    if p:
        books += [(_flip_book(b) if pf else b) for b in p["books"]]
        srcs.append(dict(name="Pinnacle (guest API)", n_books=1, ts=pts))
    if not books:
        _mcache[key] = (time.time(), None); return None
    order = {"sharp": 0, "book": 1, "consensus": 2, "open": 3}
    books.sort(key=lambda b: order[b["kind"]])
    cons = next((b for b in books if b["kind"] == "consensus"), None)
    opn = next((b for b in books if b["kind"] == "open"), None)
    sharp = next((b for b in books if b["kind"] == "sharp"), None)
    # referencia para las banderas: consenso AN si existe; si no, la mayoría
    flags = _flags(books, cons)
    for b in books:
        b["flags"] = flags.get(b["id"], {}); b["nv"] = nv_of(b)
    cnv = _consensus_nv(books, cons)
    ref_book = cons or sharp
    mv = _movement(opn, cons) if (opn and cons) else None
    sig = _signals(splits, mv, cons) if splits and any(splits.values()) else {}
    if snapshot:
        try: history.record(league, game["id"], books, splits)
        except Exception: pass
    hist = history.series(league, game["id"])
    mk = dict(sources=srcs, books=books, consensus_nv=cnv, sharp_nv=(sharp or {}).get("nv"),
              ref=dict(spread_home=_ref_line(books, "spread", "home", cons), total=_ref_line(books, "total", "over", cons)),
              splits=splits if any(splits.values()) else None, splits_src=("Action Network (agregado de casas de EE. UU.)" if splits and any(splits.values()) else None),
              splits_ts=ats if splits and any(splits.values()) else None, movement=mv, movement_src=("Apertura vs consenso (Action Network)" if mv else None),
              signals=sig, history=hist, now=time.time(),
              matched=dict(an=bool(a), pin=bool(p)))
    _mcache[key] = (time.time(), mk)
    return mk

# ---------------------------------------------------------------- señales por candidato (pick)
def attach_signals(cands, mk):
    """Añade a cada candidato: % tickets/dinero del lado, RLM / dinero inteligente a favor o en contra, y mejor precio disponible."""
    for c in cands:
        c["signals"] = cand_signals(c, mk)

def cand_signals(c, mk):
    mkt = {"ML": "ml", "Spread": "spread", "Total": "total"}.get(c.get("market"))
    out = dict(verdict="sin_dato", tags=[], tickets=None, money=None, best=None)
    if not mk or not mkt: return out
    side = c["side"]
    s = (mk.get("signals") or {}).get(mkt)
    if s:
        out["tickets"] = s["tickets"].get(side); out["money"] = (s["money"] or {}).get(side)
        score_pos = score_neg = 0
        if s["rlm"]:
            if s["rlm_side"] == side: out["tags"].append(("rlm_for", "RLM a favor: línea se mueve contra el público hacia este lado")); score_pos += 1
            elif s["public_side"] == side: out["tags"].append(("rlm_against", "RLM en contra: este es el lado público y la línea se mueve en su contra")); score_neg += 1
        elif s.get("move_dir") == "con" and s["public_side"] == side:
            out["tags"].append(("move_with", "Línea se mueve con el público en este lado"))
        if s.get("sharp_side"):
            if s["sharp_side"] == side: out["tags"].append(("sharp_for", f"Dinero > tickets (+{s['sharp_diff']} pp): lado con dinero 'más grande'")); score_pos += 1
            else: out["tags"].append(("sharp_against", f"El dinero > tickets está en el lado contrario (+{s['sharp_diff']} pp)")); score_neg += 1
        out["verdict"] = ("mixto" if score_pos and score_neg else "a_favor" if score_pos else "en_contra" if score_neg else "neutral")
    # mejor precio a la misma línea
    best = None
    for b in mk["books"]:
        if b["kind"] != "book": continue
        if mkt == "ml":
            pr = (b.get("ml") or {}).get(side); ln = None
        else:
            cell = (b.get(mkt) or {}).get(side)
            if not cell or c.get("line") is None or cell["line"] != c["line"]: continue
            pr = cell["price"]
        if pr is not None and (best is None or pr > best["price"]): best = dict(book=b["name"], price=pr)
    if best:
        best["price_txt"] = fmt_am(best["price"])
        if c.get("p_final"): best["ev"] = (c["p_final"] * am_to_dec(best["price"]) - 1) * 100
        out["best"] = best
    return out
