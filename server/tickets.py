"""Tickets / parlays de PAPEL (sin dinero): piernas de picks, juegos o props; momio combinado, prob. del modelo combinada,
avisos de piernas correlacionadas o contradictorias, guardado en SQLite y calificación automática pierna por pierna."""
import json, time, asyncio
from . import history
from . import record as R
from .odds import am_to_dec

GAME_MK = ("ml", "spread", "total", "btts", "sspread", "stotal")
_ready = False

def _c():
    global _ready
    c = history._open()
    if c is None: return None
    if not _ready:
        c.execute("""CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at INTEGER, day TEXT, name TEXT, legs TEXT,
                     status TEXT DEFAULT 'PENDIENTE', dec REAL, p_model REAL, units REAL, graded_at INTEGER, source TEXT)""")
        c.commit(); _ready = True
    return c

def reset_for_tests():
    global _ready
    _ready = False

def dec_to_am(d):
    if d is None or d <= 1: return None
    return int(round((d - 1) * 100)) if d >= 2 else int(round(-100 / (d - 1)))

# ------------------------------------------------------------------ validación y avisos
def check(legs):
    """-> dict(errors=[...], warnings=[...]). Contradicción = error (no se puede guardar); correlación = aviso."""
    err, warn = [], []
    if not legs: err.append("El ticket no tiene piernas")
    if len(legs) > 12: err.append("Máximo 12 piernas")
    seen = {}
    for i, l in enumerate(legs):
        k = l.get("kind", "game")
        if l.get("odds") is None: err.append(f"«{l.get('label')}» no tiene cuota real")
        if k == "game" and l.get("market") not in GAME_MK: err.append(f"Mercado no soportado: {l.get('market')}")
        if k == "prop" and l.get("selection") not in ("over", "under"): err.append(f"«{l.get('label')}»: sólo props de más/menos")
        g = (l.get("league"), str(l.get("eid")))
        for j in seen.get(g, []):
            m = legs[j]
            same_mk = (m.get("kind", "game"), m.get("market"), m.get("aid"), m.get("key")) == (k, l.get("market"), l.get("aid"), l.get("key"))
            if same_mk:
                if m.get("selection") != l.get("selection"): err.append(f"Contradictorias: «{m.get('label')}» y «{l.get('label')}» (lados opuestos del mismo mercado)")
                else: err.append(f"Repetida: «{l.get('label')}»")
            elif k == "game" and m.get("kind", "game") == "game" and {m.get("market"), l.get("market")} == {"ml", "spread"}:
                if m.get("selection") == l.get("selection"): warn.append(f"Correlacionadas: «{m.get('label')}» + «{l.get('label')}» (mismo lado; si gana por poco, una puede perder). Las casas suelen no permitirlas juntas.")
                else: warn.append(f"Se contradicen en parte: «{m.get('label')}» y «{l.get('label')}» (lados opuestos de ganador y hándicap)")
            else:
                warn.append(f"Mismo juego: «{m.get('label')}» + «{l.get('label')}» están correlacionadas; la prob. combinada asume independencia y puede ser engañosa")
        seen.setdefault(g, []).append(i)
    return dict(errors=list(dict.fromkeys(err)), warnings=list(dict.fromkeys(warn)))

def combine(legs):
    d = 1.0; p = 1.0; p_ok = True
    for l in legs:
        d *= am_to_dec(l["odds"])
        if l.get("p") is None: p_ok = False
        else: p *= l["p"]
    imp = 1 / d if d else None
    pm = p if p_ok else None
    return dict(dec=round(d, 4), american=dec_to_am(d), p_implied=imp, p_model=pm, ev=(pm * d - 1 if pm is not None else None))

# ------------------------------------------------------------------ CRUD
FIELDS = ("kind", "league", "eid", "sport", "start_ts", "home", "away", "home_id", "away_id", "market", "selection", "line", "odds", "label", "p", "book", "aid", "key", "player")

def create(legs, name=None, source="app", now=None):
    now = int(now or time.time())
    legs = [{k: l.get(k) for k in FIELDS} for l in (legs or [])]
    for l in legs:
        l["kind"] = l.get("kind") or "game"; l["eid"] = str(l.get("eid")); l["status"] = "PENDIENTE"
        try: l["odds"] = int(l["odds"]) if l.get("odds") is not None else None
        except Exception: l["odds"] = None
        try: l["start_ts"] = int(l["start_ts"])
        except Exception: l["start_ts"] = None
    ck = check(legs)
    for l in legs:
        if not l["start_ts"]: ck["errors"].append(f"«{l.get('label')}»: falta la hora del juego")
        elif l["start_ts"] <= now: ck["errors"].append(f"«{l.get('label')}»: el juego ya empezó (sólo se aceptan piernas pre-juego)")
    if ck["errors"]: return dict(ok=False, **ck)
    cb = combine(legs)
    day = R.cdmx_date(min(l["start_ts"] for l in legs))
    with history._lock:
        c = _c()
        cur = c.execute("INSERT INTO tickets(created_at, day, name, legs, dec, p_model, source) VALUES (?,?,?,?,?,?,?)",
                        (now, day, (name or "").strip()[:60] or None, json.dumps(legs), cb["dec"], cb["p_model"], source))
        c.commit(); tid = cur.lastrowid
    return dict(ok=True, id=tid, day=day, warnings=ck["warnings"], **cb)

def _rows(sql, args=()):
    with history._lock:
        c = _c()
        if c is None: return []
        cur = c.execute(sql, args); names = [d[0] for d in cur.description]
        out = [dict(zip(names, r)) for r in cur.fetchall()]
    for r in out: r["legs"] = json.loads(r["legs"] or "[]"); r["american"] = dec_to_am(r["dec"])
    return out

def delete(tid):
    with history._lock:
        c = _c(); n = c.execute("DELETE FROM tickets WHERE id=? AND status='PENDIENTE'", (tid,)).rowcount; c.commit()
    return n

def _agg(rows):
    W = sum(r["status"] == "GANADO" for r in rows); L = sum(r["status"] == "PERDIDO" for r in rows); P = sum(r["status"] == "PUSH" for r in rows)
    pend = sum(r["status"] == "PENDIENTE" for r in rows)
    done = [r for r in rows if r["units"] is not None]
    u = round(sum(r["units"] for r in done), 2)
    return dict(W=W, L=L, P=P, pending=pend, n=len(rows), units=u, n_priced=len(done), win_pct=(W / (W + L) * 100 if W + L else None),
                roi=(u / len(done) * 100 if done else None))

def by_day(date):
    rows = _rows("SELECT * FROM tickets WHERE day=? ORDER BY created_at DESC", (date,))
    alld = {}
    for r in _rows("SELECT * FROM tickets"): alld.setdefault(r["day"], []).append(r)
    days = [dict(date=d, **_agg(v)) for d, v in sorted(alld.items(), reverse=True)]
    return dict(date=date, tickets=rows, summary=_agg(rows), days=days, total=_agg([r for v in alld.values() for r in v]))

# ------------------------------------------------------------------ calificación
LEG_MULT = {"GANADO": None, "PUSH": 1.0, "ANULADO": 1.0, "MEDIO_PERDIDO": 0.5, "PERDIDO": 0.0}

def settle_ticket(legs):
    """-> (status, mult) con mult = pago por 1u (incluye la unidad). PENDIENTE si falta alguna pierna y aún no se perdió."""
    mult = 1.0; pend = False
    for l in legs:
        s = l.get("status", "PENDIENTE")
        if s == "PENDIENTE": pend = True; continue
        d = am_to_dec(l["odds"])
        mult *= d if s == "GANADO" else (1 + d) / 2 if s == "MEDIO_GANADO" else LEG_MULT[s]
    if mult == 0: return "PERDIDO", 0.0
    if pend: return "PENDIENTE", None
    if abs(mult - 1) < 1e-9: return "PUSH", 1.0
    return ("GANADO" if mult > 1 else "PERDIDO"), mult

async def _grade_leg(l, now):
    from . import grading as G
    if l.get("start_ts") and l["start_ts"] > now: return None
    row = dict(league=l["league"], eid=l["eid"], home_id=l.get("home_id"), away_id=l.get("away_id"), sport=l.get("sport"), market=l.get("market"),
               selection=l.get("selection"), line=l.get("line"), odds=l.get("odds"), start_ts=l.get("start_ts") or now, home=l.get("home"), away=l.get("away"))
    res = await G.fetch_result(row)
    if l.get("kind") == "prop":
        if res["state"] == "void": return "ANULADO"
        if res["state"] != "final": return None
        from . import props as P
        from .config import LEAGUES
        log = await P.gamelog(l["league"], l["aid"], need=5)
        g = next((x for x in log if str(x["eid"]) == str(l["eid"])), None)
        if not g: return "ANULADO" if now - (l.get("start_ts") or now) > 86400 else None     # no jugó (DNP): se anula como en las casas
        v = P.stat_value(LEAGUES[l["league"]]["family"], l["key"], g["s"])
        if v is None: return None
        if v == l["line"]: return "PUSH"
        return "GANADO" if ((v > l["line"]) == (l["selection"] == "over")) else "PERDIDO"
    g = G.grade_row(row, res, now)
    return g[0] if g else None

async def grade_pending(now=None):
    now = now or time.time()
    out = dict(checked=0, graded=0)
    for t in _rows("SELECT * FROM tickets WHERE status='PENDIENTE'"):
        changed = False
        for l in t["legs"]:
            if l.get("status", "PENDIENTE") != "PENDIENTE": continue
            try: st = await _grade_leg(l, now)
            except Exception: st = None
            if st: l["status"] = st; changed = True
        out["checked"] += 1
        st, mult = settle_ticket(t["legs"])
        if changed or st != "PENDIENTE":
            with history._lock:
                c = _c()
                c.execute("UPDATE tickets SET legs=?, status=?, units=?, graded_at=? WHERE id=?",
                          (json.dumps(t["legs"]), st, (round(mult - 1, 4) if mult is not None else None), int(now) if st != "PENDIENTE" else None, t["id"]))
                c.commit()
            if st != "PENDIENTE": out["graded"] += 1
    return out

# ------------------------------------------------------------------ sugerencia de parlay (chat / botón): sólo picks OFICIALES estrictos
def leg_from(game, c):
    from .data import parse_dt
    d = parse_dt(game.get("date"))
    mk = {"ML": "ml", "Spread": "spread", "Total": "total", "BTTS": "btts"}.get(c.get("market"))
    return dict(kind="game", league=game["league"], eid=str(game["id"]), sport=game.get("sport"), start_ts=int(d.timestamp()) if d else None,
                home=game["home"]["name"], away=game["away"]["name"], home_id=str(game["home"].get("id") or ""), away_id=str(game["away"].get("id") or ""),
                market=mk, selection=c.get("side"), line=c.get("line"), odds=c.get("price"), label=c.get("label"), p=c.get("p_final"), book=None)

async def suggest(n=3, scope="hoy", sport=None):
    from . import data
    d = await data.picks(scope)
    if scope == "hoy" and not any(it.get("official") for it in d["items"]): d = await data.picks("24h")
    pool = []
    for it in d["items"]:
        if sport and it["game"].get("sport") != sport: continue
        for c in (it.get("official") or [])[:1]:                     # 1 pierna por juego (sin correlación dentro del ticket)
            if c.get("price") is None or c.get("market") not in ("ML", "Spread", "Total", "BTTS"): continue
            pool.append((c.get("score") or 0, it["game"], c))
    pool.sort(key=lambda x: -x[0])
    legs, why = [], []
    for sc, g, c in pool[:max(1, min(int(n), 6))]:
        legs.append(leg_from(g, c))
        vs = f"{g['home']['name']} vs {g['away']['name']}" if g.get("sport") in ("futbol", "tenis") else f"{g['away']['name']} @ {g['home']['name']}"
        why.append(f"{c['label']} ({vs}): puntaje {sc}/100 · prob. {round(100 * (c.get('p_final') or 0))}% · edge {c.get('edge', 0):+.1f} pp"
                   + (f" · señales {((c.get('signals') or {}).get('verdict') or '').replace('_', ' ')}" if (c.get('signals') or {}).get('verdict') not in (None, 'sin_dato') else ""))
    out = dict(legs=legs, why=why, available=len(pool), asked=n, scope=d["scope"])
    if legs: out.update(combine(legs)); out.update(check(legs))
    return out
