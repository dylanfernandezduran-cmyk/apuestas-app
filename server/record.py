"""Registro de picks (pick principal y sugerencias) en SQLite + récord (G-P-E, %, unidades a 1u plano con la cuota registrada).

Reglas:
  · Sólo se registra un pick cuando se genera ANTES de que empiece el juego (estado 'pre' y hora de inicio futura).
  · Unicidad por juego + mercado + selección. Se guarda la línea/cuota de APERTURA (open_line/open_odds) y, mientras el juego no empiece,
    cada análisis re-evalúa el pick a la línea ACTUAL (pt90u): línea/cuota/probabilidades se actualizan (historial en `moves`, state=ACTUALIZADO);
    si el modelo ahora prefiere el lado contrario -> el pick viejo queda ANULADO con state=INVERTIDO y se registra el nuevo lado;
    si el mercado ya no tiene valor/lado del modelo -> ANULADO con state=CANCELADO (se reactiva si vuelve antes del inicio).
  · Al empezar el juego ya no se toca (línea de CIERRE bloqueada) y se califica contra esa línea.
  · Un juego tiene a lo sumo un pick 'main' (el primero registrado); un lean posterior distinto se guarda como 'suggestion'.
  · La calificación (ver grading.py) sólo escribe columnas de resultado; jamás toca línea/cuota/probabilidades.
  · Las filas con source != 'live' serían de relleno retroactivo (no se genera ninguna: no hay cuotas pre-juego de juegos pasados)."""
import time
from . import history
from .odds import am_to_dec

MKT = {"ML": "ml", "Spread": "spread", "Total": "total", "BTTS": "btts"}
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
        for col, typ in (("open_line", "REAL"), ("open_odds", "INTEGER"), ("state", "TEXT"), ("moves", "TEXT"), ("updated_at", "INTEGER")):
            try: c.execute(f"ALTER TABLE picks ADD COLUMN {col} {typ}")
            except Exception: pass
        c.execute("UPDATE picks SET open_line=line, open_odds=odds WHERE open_line IS NULL AND open_odds IS NULL")
        c.execute("CREATE INDEX IF NOT EXISTS ix_picks_status ON picks(status, start_ts)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_picks_game ON picks(league, eid)")
        c.execute("CREATE TABLE IF NOT EXISTS team_logos(league TEXT, team_id TEXT, logo TEXT, PRIMARY KEY(league, team_id))")
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
    # pt9x (estricto): sólo se registran los picks OFICIALES (máx. 2 por juego); ya no se registran sugerencias/alternativas
    for i, c in enumerate(a["picks"].get("official") or []):
        if not MKT.get(c.get("market")) or not c.get("side"): continue
        out.append(mk(market=MKT[c["market"]], selection=c["side"], line=c.get("line"), label=c["label"], odds=c.get("price"),
                      book=(book if c.get("price") is not None else None), p_model=c.get("p_model"), p_final=c.get("p_final"), p_nv=c.get("p_nv"),
                      edge=c.get("edge"), basis="modelo", type="main" if i == 0 else "suggestion"))
    return out

def record_analysis(a, now=None):
    """Persiste los picks de un análisis. Devuelve cuántas filas nuevas se insertaron."""
    rows = extract(a, now)
    if not rows:
        # sin pick oficial: los picks pendientes ya registrados de este juego (aún sin empezar) se cancelan (criterio estricto)
        g = (a or {}).get("game") or {}
        if a and a.get("picks") is not None and g.get("state") == "pre":
            try: reconcile([], now, key=(g["league"], str(g["id"])))
            except Exception: pass
        return 0
    try: reconcile(rows, now)
    except Exception: pass
    return record_rows(rows)

def _fresh_by_market(rows):
    out = {}
    for r in rows:                      # el 1º de cada mercado (el principal va primero)
        out.setdefault(r["market"], r)
    return out

def reconcile(rows, now=None, key=None):
    """Re-evalúa los picks YA registrados de este juego contra el análisis actual (sólo antes del inicio). Devuelve dict de conteos."""
    import json
    now = int(now or time.time())
    if not rows and not key: return {}
    lg, eid = (rows[0]["league"], rows[0]["eid"]) if rows else key
    fresh = _fresh_by_market(rows)
    cnt = dict(updated=0, flipped=0, cancelled=0, reactivated=0)
    with history._lock:
        c = _c()
        if c is None: return cnt
        cur = c.execute("SELECT id, market, selection, line, odds, open_line, open_odds, status, state, moves, label FROM picks WHERE league=? AND eid=? AND start_ts>? "
                        "AND (status='PENDIENTE' OR (status='ANULADO' AND state IN ('CANCELADO','INVERTIDO')))", (lg, eid, now))
        for pid, mk, sel, line, odds, oline, oodds, status, state, moves, label in cur.fetchall():
            mv = json.loads(moves) if moves else []
            f = fresh.get(mk)
            if f and f["selection"] == sel:
                changed = (f.get("line") != line) or (f.get("odds") != odds)
                if changed: mv.append(dict(t=now, line=f.get("line"), odds=f.get("odds")))
                moved = (f.get("line") != oline) or (f.get("odds") != oodds)
                new_state = "ACTUALIZADO" if moved else "ACTIVO"
                if status == "ANULADO": cnt["reactivated"] += 1
                elif changed: cnt["updated"] += 1
                c.execute("UPDATE picks SET line=?, odds=?, label=?, book=COALESCE(?, book), p_model=?, p_final=?, p_nv=?, edge=?, status='PENDIENTE', state=?, moves=?, updated_at=?, "
                          "note=CASE WHEN ?='ANULADO' THEN NULL ELSE note END WHERE id=?",
                          (f.get("line"), f.get("odds"), f["label"], f.get("book"), f.get("p_model"), f.get("p_final"), f.get("p_nv"), f.get("edge"), new_state,
                           json.dumps(mv), now, status, pid))
            elif status == "PENDIENTE":
                if f:
                    c.execute("UPDATE picks SET status='ANULADO', state='INVERTIDO', updated_at=?, note=? WHERE id=?",
                              (now, f"Invertido antes del inicio: a la línea actual el modelo prefiere {f['label']}", pid)); cnt["flipped"] += 1
                else:
                    c.execute("UPDATE picks SET status='ANULADO', state='CANCELADO', updated_at=?, note=? WHERE id=?",
                              (now, "Cancelado antes del inicio: a la línea actual ya no pasa el filtro de pick oficial (edge/probabilidad/señales/coherencia)", pid)); cnt["cancelled"] += 1
        c.commit()
    return cnt

def record_rows(rows):
    n = 0
    with history._lock:
        c = _c()
        if c is None: return 0
        for r in rows:
            # una sola selección por juego+mercado (la primera registrada): si luego el modelo prefiere el lado contrario (la línea se movió),
            # NO se registra para no contar ambos lados de un mismo mercado como dos picks
            if c.execute("SELECT 1 FROM picks WHERE league=? AND eid=? AND market=? AND selection<>? AND status<>'ANULADO'", (r["league"], r["eid"], r["market"], r["selection"])).fetchone():
                continue
            has_main = c.execute("SELECT 1 FROM picks WHERE league=? AND eid=? AND type='main' AND status<>'ANULADO'", (r["league"], r["eid"])).fetchone()
            typ = r["type"] if not (r["type"] == "main" and has_main) else "suggestion"
            vals = (r["sport"], r["league"], r["eid"], r["start_ts"], r["home"], r["away"], r["home_id"], r["away_id"], r["market"], r["selection"], r["line"], r["label"],
                    r["odds"], r["book"], r["p_model"], r["p_final"], r["p_nv"], r["edge"], r["basis"], typ, r["created_at"], r["source"])
            cur = c.execute(f"INSERT OR IGNORE INTO picks({COLS}) VALUES ({','.join('?' * 22)})", vals)
            if cur.rowcount:
                n += 1
                c.execute("UPDATE picks SET open_line=line, open_odds=odds, state='ACTIVO' WHERE id=?", (cur.lastrowid,))
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
    return _rows(f"SELECT p.*, (SELECT logo FROM team_logos t WHERE t.league=p.league AND t.team_id=p.home_id) AS home_logo, "
                 f"(SELECT logo FROM team_logos t WHERE t.league=p.league AND t.team_id=p.away_id) AS away_logo "
                 f"FROM picks p WHERE {' AND '.join(w)} ORDER BY start_ts DESC, id DESC LIMIT ?", (*a, limit))

# ------------------------------------------------------------------ logos de equipos (para el récord: los picks sólo guardan ids)
_LOGO_SEEN = {}

def remember_logos(league, games):
    """Guarda (liga, id de equipo) -> logo/foto vistos en los marcadores, para mostrarlos en el historial. Sólo escribe si cambió."""
    new = []
    for g in games or []:
        for sd in ("home", "away"):
            t = g.get(sd) or {}
            tid, lg = str(t.get("id") or ""), t.get("logo")
            if tid and lg and _LOGO_SEEN.get((league, tid)) != lg:
                _LOGO_SEEN[(league, tid)] = lg; new.append((league, tid, lg))
    if not new: return 0
    with history._lock:
        c = _c()
        if c is None: return 0
        c.execute("CREATE TABLE IF NOT EXISTS team_logos(league TEXT, team_id TEXT, logo TEXT, PRIMARY KEY(league, team_id))")
        c.executemany("INSERT OR REPLACE INTO team_logos(league, team_id, logo) VALUES (?,?,?)", new)
        c.commit()
    return len(new)

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

# ------------------------------------------------------------------ récord por día (pt92u): días en hora de CDMX (UTC-6 fijo, México sin horario de verano)
CDMX_OFF = -6 * 3600
_DAY_SQL = f"date(start_ts + ({CDMX_OFF}), 'unixepoch')"

def cdmx_date(ts=None):
    return time.strftime("%Y-%m-%d", time.gmtime((ts if ts is not None else time.time()) + CDMX_OFF))

def _agg(rows):
    W = L = P = 0.0; u = 0.0; npr = 0; pend = void = 0
    for r in rows:
        s = r["status"]
        if s == "GANADO": W += 1
        elif s == "PERDIDO": L += 1
        elif s == "PUSH": P += 1
        elif s == "MEDIO_GANADO": W += .5; P += .5
        elif s == "MEDIO_PERDIDO": L += .5; P += .5
        elif s == "PENDIENTE": pend += 1
        elif s == "ANULADO": void += 1
        if s in DONE and r.get("units") is not None: u += r["units"]; npr += 1
    return dict(W=W, L=L, P=P, pending=pend, void=void, n=len(rows), units=round(u, 2), n_priced=npr,
                win_pct=(W / (W + L) * 100 if W + L else None), roi=(u / npr * 100 if npr else None))

def days(sport=None, typ=None):
    """Lista de días con picks: [{date, W, L, P, pending, void, units, ...}] (más reciente primero)."""
    w, a = ["1=1"], []
    if sport: w.append("sport=?"); a.append(sport)
    if typ in ("main", "suggestion"): w.append("type=?"); a.append(typ)
    by = {}
    for r in _rows(f"SELECT {_DAY_SQL} AS d, status, units FROM picks WHERE {' AND '.join(w)}", tuple(a)):
        by.setdefault(r["d"], []).append(r)
    return [dict(date=d, **_agg(rs)) for d, rs in sorted(by.items(), reverse=True)]

def day(date):
    """Todos los picks (cualquier estado) cuyo juego es en `date` (YYYY-MM-DD, CDMX) + resumen total y por deporte."""
    rows = _rows("SELECT p.*, (SELECT logo FROM team_logos t WHERE t.league=p.league AND t.team_id=p.home_id) AS home_logo, "
                 "(SELECT logo FROM team_logos t WHERE t.league=p.league AND t.team_id=p.away_id) AS away_logo "
                 f"FROM picks p WHERE {_DAY_SQL}=? ORDER BY start_ts, eid, (type='main') DESC, id", (date,))
    sp = {}
    for r in rows: sp.setdefault(r["sport"], []).append(r)
    return dict(summary=_agg(rows), by_sport={k: _agg(v) for k, v in sp.items()}, picks=rows)
