"""Registro de picks (pick principal y sugerencias) en SQLite + récord (G-P-E, %, unidades a 1u plano con la cuota registrada).

Reglas:
  · Sólo se registra un pick cuando se genera ANTES de que empiece el juego (estado 'pre' y hora de inicio futura).
  · Unicidad por juego + mercado + selección: se conserva la PRIMERA línea/cuota registrada (INSERT OR IGNORE; nunca se sobrescribe).
  · Además, una sola selección por juego+mercado (la primera): el lado contrario del mismo mercado no se registra después.
  · Un juego tiene a lo sumo un pick 'main' (el primero registrado); un lean posterior distinto se guarda como 'suggestion'.
  · La calificación (ver grading.py) sólo escribe columnas de resultado; jamás toca línea/cuota/probabilidades.
  · Las filas con source != 'live' serían de relleno retroactivo (no se genera ninguna: no hay cuotas pre-juego de juegos pasados)."""
import time
from . import history
from .odds import am_to_dec

MKT = {"ML": "ml", "Spread": "spread", "Total": "total"}
DONE = ("GANADO", "PERDIDO", "PUSH", "MEDIO_GANADO", "MEDIO_PERDIDO")
STATUSES = DONE + ("ANULADO", "PENDIENTE")
_ready = False

COLS = ("sport,league,eid,start_ts,home,away,home_id,away_id,market,selection,line,label,odds,book,p_model,p_final,p_nv,edge,basis,type,created_at,source")

def _c():
    """Conexión compartida con history (misma base SQLite). Llamar con history._lock tomado."""
    global _ready
    c = history._open()
    if c is None: return None
    if not _ready or not _table_ok(c):
        c.execute("""CREATE TABLE IF NOT EXISTS picks(
            id INTEGER PRIMARY KEY AUTOINCREMENT, sport TEXT, league TEXT, eid TEXT, start_ts INTEGER, home TEXT, away TEXT, home_id TEXT, away_id TEXT,
            market TEXT, selection TEXT, line REAL, label TEXT, odds INTEGER, book TEXT, p_model REAL, p_final REAL, p_nv REAL, edge REAL, basis TEXT,
            type TEXT, created_at INTEGER, source TEXT DEFAULT 'live',
            status TEXT DEFAULT 'PENDIENTE', units REAL, graded_at INTEGER, score_text TEXT, final_home REAL, final_away REAL, note TEXT,
            UNIQUE(league, eid, market, selection))""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_picks_status ON picks(status, start_ts)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_picks_game ON picks(league, eid)")
        # fútbol: el marcador guardado como "visitante X @ local Y" pasa a "local Y - X visitante" (local primero)
        c.execute("""UPDATE picks SET score_text = home || ' ' || CAST(final_home AS INTEGER) || ' - ' || CAST(final_away AS INTEGER) || ' ' || away
                     WHERE sport='futbol' AND score_text LIKE '% @ %' AND final_home IS NOT NULL AND final_away IS NOT NULL""")
        c.commit(); _ready = True
    return c

def _table_ok(c):
    try: c.execute("SELECT 1 FROM picks LIMIT 1"); return True
    except Exception: return False

def reset_for_tests():
    global _ready
    _ready = False

# ------------------------------------------------------------------ extracción desde el análisis de un juego
def extract(a, now=None):
    """a: salida de data.analyze(). Devuelve lista de dicts de picks (main primero) o [] si no aplica (juego iniciado / sin picks)."""
    now = now or time.time()
    if not a or not a.get("picks"): return []
    g = a["game"]
    if g.get("state") != "pre": return []
    from .data import parse_dt
    d = parse_dt(g.get("date"))
    if not d or d.timestamp() <= now: return []
    start = int(d.timestamp())
    base = dict(sport=g["sport"], league=g["league"], eid=str(g["id"]), start_ts=start, home=g["home"]["name"], away=g["away"]["name"],
                home_id=str(g["home"].get("id") or ""), away_id=str(g["away"].get("id") or ""), created_at=int(now), source="live")
    book = (a.get("odds") or {}).get("book")
    out = []
    def mk(**kw):
        r = dict(base); r.update(kw); return r
    lean = a["picks"]["lean"]
    if lean and MKT.get(lean.get("market")) and lean.get("side"):
        out.append(mk(market=MKT[lean["market"]], selection=lean["side"], line=lean.get("line"), label=lean["label"], odds=lean.get("price"),
                      book=(book if lean.get("price") is not None else None), p_model=lean.get("p_model"), p_final=lean.get("p_final"), p_nv=lean.get("p_nv"),
                      edge=lean.get("edge"), basis="modelo", type="main"))
    # sugerencias 1: candidatos del modelo con ventaja (PICK / LEAN) distintos del principal
    for c in a["picks"].get("candidates") or []:
        if c is lean or not MKT.get(c.get("market")) or c.get("status") not in ("PICK", "LEAN"): continue
        out.append(mk(market=MKT[c["market"]], selection=c["side"], line=c.get("line"), label=c["label"], odds=c.get("price"), book=(book if c.get("price") is not None else None),
                      p_model=c.get("p_model"), p_final=c.get("p_final"), p_nv=c.get("p_nv"), edge=c.get("edge"), basis="modelo", type="suggestion"))
    # sugerencias 2: mejor resultado por mercado de la sección Probabilidades (lo que muestran las tarjetas de lista / Top picks)
    from . import probs as PR
    for b in PR.brief(a.get("probs")):
        if not b.get("side") or not b.get("market"): continue
        best = b.get("best") or {}
        out.append(mk(market=b["market"], selection=b["side"], line=b.get("line"), label=b["label"], odds=best.get("price"), book=best.get("book"),
                      p_model=b.get("p_model"), p_final=b.get("p_final"), p_nv=b.get("p_nv"), edge=b.get("edge"),
                      basis=("modelo" if b.get("p_model") is not None else "mercado"), type="suggestion"))
    return out

def record_analysis(a, now=None):
    """Persiste los picks de un análisis. Devuelve cuántas filas nuevas se insertaron."""
    rows = extract(a, now)
    if not rows: return 0
    return record_rows(rows)

def record_rows(rows):
    n = 0
    with history._lock:
        c = _c()
        if c is None: return 0
        for r in rows:
            # una sola selección por juego+mercado (la primera registrada): si luego el modelo prefiere el lado contrario (la línea se movió),
            # NO se registra para no contar ambos lados de un mismo mercado como dos picks
            if c.execute("SELECT 1 FROM picks WHERE league=? AND eid=? AND market=? AND selection<>?", (r["league"], r["eid"], r["market"], r["selection"])).fetchone():
                continue
            has_main = c.execute("SELECT 1 FROM picks WHERE league=? AND eid=? AND type='main'", (r["league"], r["eid"])).fetchone()
            typ = r["type"] if not (r["type"] == "main" and has_main) else "suggestion"
            vals = (r["sport"], r["league"], r["eid"], r["start_ts"], r["home"], r["away"], r["home_id"], r["away_id"], r["market"], r["selection"], r["line"], r["label"],
                    r["odds"], r["book"], r["p_model"], r["p_final"], r["p_nv"], r["edge"], r["basis"], typ, r["created_at"], r["source"])
            cur = c.execute(f"INSERT OR IGNORE INTO picks({COLS}) VALUES ({','.join('?' * 22)})", vals)
            if cur.rowcount: n += 1
            elif typ == "main" and not has_main:
                # el pick ya existía como sugerencia y el juego aún no tenía principal: se asciende (línea/cuota registradas NO cambian)
                c.execute("UPDATE picks SET type='main' WHERE league=? AND eid=? AND market=? AND selection=? AND type='suggestion' AND status='PENDIENTE'",
                          (r["league"], r["eid"], r["market"], r["selection"]))
        c.commit()
    return n

# ------------------------------------------------------------------ consultas
def _rows(sql, args=()):
    with history._lock:
        c = _c()
        if c is None: return []
        cur = c.execute(sql, args)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]

def game_rows(league, eid):
    return _rows("SELECT * FROM picks WHERE league=? AND eid=? ORDER BY (type='main') DESC, id", (league, str(eid)))

def games_rows(league, eids):
    eids = [str(e) for e in eids]
    if not eids: return {}
    out = {}
    for r in _rows(f"SELECT * FROM picks WHERE league=? AND eid IN ({','.join('?' * len(eids))}) ORDER BY (type='main') DESC, id", (league, *eids)):
        out.setdefault(r["eid"], []).append(r)
    return out

def pending(now=None, limit=500):
    """Picks sin calificar cuyo juego ya empezó."""
    now = int(now or time.time())
    return _rows("SELECT * FROM picks WHERE status='PENDIENTE' AND start_ts<=? ORDER BY start_ts LIMIT ?", (now, limit))

def set_grade(pid, status, units, score_text, fh, fa, note, now=None):
    """Escribe SÓLO columnas de resultado."""
    with history._lock:
        c = _c()
        if c is None: return
        c.execute("UPDATE picks SET status=?, units=?, graded_at=?, score_text=?, final_home=?, final_away=?, note=? WHERE id=?",
                  (status, units, int(now or time.time()), score_text, fh, fa, note, pid))
        c.commit()

def set_note(pid, note):
    with history._lock:
        c = _c()
        if c is None: return
        c.execute("UPDATE picks SET note=? WHERE id=? AND status='PENDIENTE'", (note, pid)); c.commit()

def profit(status, odds):
    """Unidades ganadas/perdidas a 1u plano con la cuota registrada. None si no hay cuota (o es anulado/pendiente)."""
    if status in ("PENDIENTE", "ANULADO"): return None
    if status == "PUSH": return 0.0
    if status == "PERDIDO": return -1.0
    if status == "MEDIO_PERDIDO": return -0.5
    if odds is None: return None
    d = am_to_dec(odds) - 1
    return round(d if status == "GANADO" else d / 2, 4)

def query(sport=None, typ=None, days=None, limit=60, league=None, basis=None):
    w, a = ["status IN ('GANADO','PERDIDO','PUSH','MEDIO_GANADO','MEDIO_PERDIDO')"], []
    if sport: w.append("sport=?"); a.append(sport)
    if league: w.append("league=?"); a.append(league)
    if typ in ("main", "suggestion"): w.append("type=?"); a.append(typ)
    if basis in ("modelo", "mercado"): w.append("basis=?"); a.append(basis)
    if days: w.append("start_ts>=?"); a.append(int(time.time() - days * 86400))
    return _rows(f"SELECT * FROM picks WHERE {' AND '.join(w)} ORDER BY start_ts DESC, id DESC LIMIT ?", (*a, limit))

def summary(sport=None, typ=None, days=None, basis=None):
    """Récord agregado. Medio ganado = 0.5 G + 0.5 E; medio perdido = 0.5 P + 0.5 E (se muestran como decimales sólo si existen)."""
    w, a = ["1=1"], []
    if sport: w.append("sport=?"); a.append(sport)
    if typ in ("main", "suggestion"): w.append("type=?"); a.append(typ)
    if basis in ("modelo", "mercado"): w.append("basis=?"); a.append(basis)
    if days: w.append("start_ts>=?"); a.append(int(time.time() - days * 86400))
    since = _rows("SELECT MIN(created_at) m FROM picks")[0]["m"]
    rows = _rows(f"SELECT status, odds, units, source FROM picks WHERE {' AND '.join(w)}", tuple(a))
    cnt = {s: 0 for s in STATUSES}
    units = 0.0; n_priced = 0; n_unpriced = 0
    for r in rows:
        cnt[r["status"]] = cnt.get(r["status"], 0) + 1
        if r["status"] in DONE:
            if r["units"] is None: n_unpriced += 1
            else: units += r["units"]; n_priced += 1
    W = cnt["GANADO"] + 0.5 * cnt["MEDIO_GANADO"]
    L = cnt["PERDIDO"] + 0.5 * cnt["MEDIO_PERDIDO"]
    P = cnt["PUSH"] + 0.5 * (cnt["MEDIO_GANADO"] + cnt["MEDIO_PERDIDO"])
    graded = sum(cnt[s] for s in DONE)
    return dict(total=len(rows), graded=graded, pending=cnt["PENDIENTE"], void=cnt["ANULADO"], counts=cnt, W=W, L=L, P=P,
                win_pct=(W / (W + L) * 100 if (W + L) else None), units=round(units, 2), n_priced=n_priced, n_unpriced=n_unpriced,
                roi=(units / n_priced * 100 if n_priced else None),
                backfilled=sum(1 for r in rows if r["source"] != "live"), since=since)
