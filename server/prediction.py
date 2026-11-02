"""Predicción NRNM: marcador proyectado + ganador + total + hándicap, DERIVADOS de las proyecciones del modelo (nada inventado).
 · Fútbol: matriz de Poisson de goles -> marcador más probable DENTRO del resultado 1X2 pronosticado.
 · NBA/NFL/NHL/MLB: margen y total proyectados por el modelo -> puntos/carreras por equipo redondeados (marcador exacto de mayor probabilidad cerca de la proyección).
 · Tenis: modelo de sets/juegos (ranking -> prob. de partido -> prob. de set -> prob. de juego) -> marcador por sets más probable.
Total y hándicap sólo se muestran si existe línea de mercado. Se guarda ANTES de que empiece el juego (se actualiza mientras no haya empezado) y se bloquea al inicio.
Se califica con el marcador final real (mismas reglas de grading.py) en una tabla aparte `predictions` y su propio récord de aciertos."""
import json, math, time
from . import history, record as REC
from .odds import norm_cdf
from .model import pois_pmf, cover_normal, cover_matrix

PT = ("ml", "total", "spread", "score")     # tipos de acierto: ganador, total, hándicap, marcador exacto

# ------------------------------------------------------------------ construcción
def _soccer(mdl, odds, g):
    lh, la = mdl["lam_home"], mdl["lam_away"]
    ph, pa = pois_pmf(lh), pois_pmf(la)
    mat = [[a * b for b in pa] for a in ph]; tot = sum(map(sum, mat)); mat = [[x / tot for x in r] for r in mat]
    p = dict(home=mdl["p_home"], draw=mdl["p_draw"], away=mdl["p_away"])
    w = max(p, key=p.get)
    cond = {"home": lambda i, j: i > j, "draw": lambda i, j: i == j, "away": lambda i, j: i < j}[w]
    h, a = max(((i, j) for i in range(len(mat)) for j in range(len(mat)) if cond(i, j)), key=lambda x: mat[x[0]][x[1]])
    out = dict(kind="poisson", winner=dict(side=w, p=p[w], probs=p), score=dict(home=h, away=a, p=mat[h][a]), proj=dict(home=lh, away=la, total=lh + la, margin=lh - la))
    return out, mdl["total"], mdl["cover"]

def _pmass(x, mu, sg): return norm_cdf((x + .5 - mu) / sg) - norm_cdf((x - .5 - mu) / sg)

def _margin(mdl, odds, g):
    T, mu, sg, ts = mdl["exp_total"], mdl["mu"], mdl["sigma"], mdl["tsigma"]
    hp, ap = (T + mu) / 2, (T - mu) / 2
    h0, a0 = max(0, int(round(hp))), max(0, int(round(ap)))
    w = "home" if mu >= 0 else "away"
    best = None
    for h in range(max(0, h0 - 8), h0 + 9):
        for a in range(max(0, a0 - 8), a0 + 9):
            if h == a or (h > a) != (w == "home"): continue
            p = 2 * _pmass(h - a, mu, sg) * _pmass(h + a, T, ts)
            if best is None or p > best[0]: best = (p, h, a)
    if best is None: return None, None, None
    p = dict(home=mdl["p_home"], away=mdl["p_away"])
    out = dict(kind="margen", winner=dict(side=w, p=p[w], probs=p), score=dict(home=best[1], away=best[2], p=best[0]), proj=dict(home=hp, away=ap, total=T, margin=mu))
    return out, mdl["total"], mdl["cover"]

# --- tenis: set/juego
def _set_dist(pg):
    """Distribución del marcador de un set (juegos i.i.d. con prob pg para el jugador A; desempate 7-6 con la misma prob). -> {(a,b): p}."""
    q = 1 - pg; d = {}
    for k in range(0, 5):
        c = math.comb(5 + k, k)
        d[(6, k)] = c * pg ** 6 * q ** k
        d[(k, 6)] = c * q ** 6 * pg ** k
    c55 = math.comb(10, 5) * (pg * q) ** 5
    d[(7, 5)] = c55 * pg * pg; d[(5, 7)] = c55 * q * q
    p66 = c55 * 2 * pg * q
    d[(7, 6)] = p66 * pg; d[(6, 7)] = p66 * q
    z = sum(d.values())
    return {k: v / z for k, v in d.items()}

def _set_win(pg): return sum(v for (a, b), v in _set_dist(pg).items() if a > b)

def _match_dist(pg, best_of):
    """-> {(sets_a, sets_b, games_a, games_b): p}"""
    need = best_of // 2 + 1
    sd = list(_set_dist(pg).items())
    cur = {(0, 0, 0, 0): 1.0}; done = {}
    while cur:
        nxt = {}
        for (sa, sb, ga, gb), p in cur.items():
            for (a, b), q in sd:
                s1, s2 = sa + (a > b), sb + (b > a); k = (s1, s2, ga + a, gb + b); pr = p * q
                if s1 == need or s2 == need: done[k] = done.get(k, 0) + pr
                else: nxt[k] = nxt.get(k, 0) + pr
        cur = nxt
    return done

def _match_win(pg, best_of):
    return sum(v for (sa, sb, _, _), v in _match_dist(pg, best_of).items() if sa > sb)

def _solve(f, target):
    lo, hi = 0.02, 0.98
    for _ in range(40):
        mid = (lo + hi) / 2
        if f(mid) < target: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def _tennis(mdl, odds, g):
    bo = g.get("best_of") or 3
    pm = mdl["p_home"]
    pg = _solve(lambda x: _match_win(x, bo), pm)
    dist = _match_dist(pg, bo); sd = _set_dist(pg)
    w = "home" if pm >= .5 else "away"
    # resultado por sets más probable del ganador pronosticado
    byres = {}
    for (sa, sb, _, _), v in dist.items():
        if (sa > sb) == (w == "home"): byres[(sa, sb)] = byres.get((sa, sb), 0) + v
    sets_res = max(byres, key=byres.get)
    nw, nl = (sets_res if w == "home" else sets_res[::-1])      # sets del ganador / del perdedor
    win_sc = max(((a, b) for (a, b) in sd if (a > b) == (w == "home")), key=lambda k: sd[k])
    los_sc = max(((a, b) for (a, b) in sd if (a > b) != (w == "home")), key=lambda k: sd[k])
    # los sets son i.i.d. en el modelo: cualquier orden tiene la misma probabilidad; se muestra el perdedor ganando el 1º (patrón habitual) cuando hay 2-1
    order = ["w"] * nw if nl == 0 else (["w", "l"] * 5)[:nw + nl - 1] + ["w"]
    sets = [win_sc if o == "w" else los_sc for o in order]            # (juegos local, juegos visita) por set
    p_seq = math.comb(nw + nl, nl) and 1.0
    for sc in sets: p_seq *= sd[sc]
    gh = sum(a for a, b in sets); ga = sum(b for a, b in sets)
    eg = sum((k[2] + k[3]) * v for k, v in dist.items()); em = sum((k[2] - k[3]) * v for k, v in dist.items())
    out = dict(kind="tenis", winner=dict(side=w, p=max(pm, 1 - pm), probs=dict(home=pm, away=1 - pm)),
               score=dict(home=nw if w == "home" else nl, away=nl if w == "home" else nw, p=byres[sets_res], sets=[list(s) for s in sets], p_seq=p_seq, games=[gh, ga]),
               proj=dict(total=eg, margin=em, pg=pg, best_of=bo))
    def total(t):
        win = sum(v for k, v in dist.items() if k[2] + k[3] > t); loss = sum(v for k, v in dist.items() if k[2] + k[3] < t)
        z = win + loss; return (win / z, loss / z, 1 - z) if z else (.5, .5, 0)
    def cover(t):
        win = sum(v for k, v in dist.items() if (k[2] - k[3]) > t); loss = sum(v for k, v in dist.items() if (k[2] - k[3]) < t)
        z = win + loss; return (win / z, loss / z, 1 - z) if z else (.5, .5, 0)
    return out, total, cover

def build(game, mdl, odds, fam, corners=None):
    """Predicción para un juego PRE o None si no hay modelo suficiente. corners: salida de corners_info() (sólo fútbol, datos reales de ESPN)."""
    if not mdl: return None
    try:
        if fam == "tennis": out, total, cover = _tennis(mdl, odds, game)
        elif fam == "soccer": out, total, cover = _soccer(mdl, odds, game)
        else: out, total, cover = _margin(mdl, odds, game)
    except Exception:
        return None
    if not out: return None
    tt = (odds or {}).get("total") or {}
    T, src = None, None
    if "over" in tt and tt["over"].get("line") is not None and (tt["over"]["line"] * 4) % 2 == 0: T, src = tt["over"]["line"], "mercado"
    elif fam == "soccer": T, src = 2.5, "modelo"          # sin línea de mercado: la línea estándar de fútbol (2.5), marcada como del modelo
    if T is not None:
        w, l, _ = total(T)
        side = "over" if w >= l else "under"
        out["total"] = dict(line=T, line_src=src, side=side, p=max(w, l), p_over=w, proj=out["proj"].get("total"), label=f"{'Más' if side == 'over' else 'Menos'} de {T:g}")
    sp = (odds or {}).get("spread") or {}
    if "home" in sp and sp["home"].get("line") is not None and (sp["home"]["line"] * 4) % 2 == 0:
        L = sp["home"]["line"]
        ph, pa = cover(-L)[0], cover(-L)[1]
        side = "home" if ph >= pa else "away"
        out["spread"] = dict(line=L, line_src="mercado", side=side, p=max(ph, pa), p_home=ph, p_away=pa, proj=out["proj"].get("margin"))
    elif fam == "soccer":
        # sin hándicap de mercado: el hándicap más exigente (−1.5 / −0.5) que el ganador pronosticado cubre con ≥50% según el modelo (línea del modelo)
        w = out["winner"]["side"]
        if w in ("home", "away"):
            for Lw in (1.5, 0.5):
                L = -Lw if w == "home" else Lw          # línea del LOCAL
                pc = cover(-L)[0] if w == "home" else cover(-L)[1]
                if pc >= 0.5:
                    out["spread"] = dict(line=L, line_src="modelo", side=w, p=pc, p_home=cover(-L)[0], p_away=cover(-L)[1], proj=out["proj"].get("margin")); break
    if corners and fam == "soccer":
        c = corners; line = c["line"]; mu, sd = c["total"], c["sd"]
        w, l, _ = cover_normal(mu, sd, line)
        side = "over" if w >= l else "under"
        out["corners"] = dict(line=line, line_src="promedio", side=side, p=max(w, l), proj=mu, home=c["home"], away=c["away"], n=c["n"],
                              label=f"{'Más' if side == 'over' else 'Menos'} de {line:g} córners")
    out["book"] = (odds or {}).get("book")
    return out

# ------------------------------------------------------------------ córners (datos reales de ESPN: wonCorners del boxscore de los últimos partidos)
def corners_of(summ):
    """summary de ESPN -> {homeAway: corners} (o None si el boxscore no trae córners)."""
    out = {}
    for t in ((summ or {}).get("boxscore") or {}).get("teams") or []:
        st = next((x for x in t.get("statistics", []) if x.get("name") == "wonCorners"), None)
        try: out[t.get("homeAway")] = int(float(st["displayValue"]))
        except Exception: return None
    return out if "home" in out and "away" in out else None

async def corners_info(league, path, tsum_h, tsum_a, hid, aid, n=6):
    """Promedios de córners a favor/en contra de cada equipo en sus últimos `n` partidos + proyección del partido. None si no hay datos reales suficientes."""
    import asyncio, statistics
    from .cache import get_json
    from .config import ESPN
    async def one(row):
        d = await get_json(f"{ESPN}/{path}/summary", ttl=21600, params={"event": row["id"]})
        c = corners_of(d)
        if not c: return None
        mine, theirs = (c["home"], c["away"]) if row["home"] else (c["away"], c["home"])
        return dict(f=mine, a=theirs)
    async def side(ts):
        rows = (ts.get("recent") or [])[:n]
        try: res = await asyncio.wait_for(asyncio.gather(*[one(r) for r in rows]), 12)
        except Exception: return []
        return [r for r in res if r]
    H, A = await asyncio.gather(side(tsum_h), side(tsum_a))
    if len(H) < 4 or len(A) < 4: return None
    avg = lambda L, k: sum(x[k] for x in L) / len(L)
    ph = (avg(H, "f") + avg(A, "a")) / 2; pa = (avg(A, "f") + avg(H, "a")) / 2
    totals = [x["f"] + x["a"] for x in H + A]
    mean = sum(totals) / len(totals)
    return dict(home=ph, away=pa, total=ph + pa, line=round(mean - .5) + .5, sd=max(2.0, statistics.pstdev(totals)), n=[len(H), len(A)])

# ------------------------------------------------------------------ almacenamiento (tabla propia en la misma base SQLite)
def _c():
    c = REC._c()
    if c is None: return None
    c.execute("""CREATE TABLE IF NOT EXISTS predictions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, sport TEXT, league TEXT, eid TEXT, start_ts INTEGER, home TEXT, away TEXT, home_id TEXT, away_id TEXT,
        payload TEXT, created_at INTEGER, updated_at INTEGER, status TEXT DEFAULT 'PENDIENTE', graded_at INTEGER,
        r_ml TEXT, r_total TEXT, r_spread TEXT, r_score TEXT, r_sets TEXT, r_corners TEXT, score_text TEXT, final_home REAL, final_away REAL, note TEXT,
        UNIQUE(league, eid))""")
    try: c.execute("ALTER TABLE predictions ADD COLUMN r_corners TEXT")
    except Exception: pass
    return c

def _rows(sql, args=()):
    with history._lock:
        c = _c()
        if c is None: return []
        cur = c.execute(sql, args)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]

def save(game, pred, now=None):
    """Guarda/actualiza la predicción SÓLO mientras el juego no haya empezado (bloqueada desde el inicio). Devuelve True si escribió."""
    from .data import parse_dt
    now = now or time.time()
    if not pred or game.get("state") != "pre": return False
    d = parse_dt(game.get("date"))
    if not d or d.timestamp() <= now: return False
    start = int(d.timestamp())
    with history._lock:
        c = _c()
        if c is None: return False
        c.execute("""INSERT INTO predictions(sport,league,eid,start_ts,home,away,home_id,away_id,payload,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(league,eid) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at, start_ts=excluded.start_ts
                     WHERE predictions.status='PENDIENTE' AND predictions.start_ts>?""",
                  (game["sport"], game["league"], str(game["id"]), start, game["home"]["name"], game["away"]["name"], str(game["home"].get("id") or ""), str(game["away"].get("id") or ""),
                   json.dumps(pred), int(now), int(now), int(now)))
        c.commit()
    return True

def get(league, eid):
    r = _rows("SELECT * FROM predictions WHERE league=? AND eid=?", (league, str(eid)))
    if not r: return None
    r = r[0]; r["pred"] = json.loads(r.pop("payload") or "null"); return r

def attach(out, now=None):
    """Para /api/game: pre -> predicción vigente (se guarda); en vivo/final -> la predicción BLOQUEADA guardada antes del inicio (con su calificación si ya terminó)."""
    now = now or time.time()
    if not out: return out
    g = out["game"]; fresh = out.pop("pred", None)
    from .data import parse_dt
    d = parse_dt(g.get("date")); started = (not d) or d.timestamp() <= now or g.get("state") != "pre"
    row = None
    if not started and fresh:
        try: save(g, fresh, now)
        except Exception: pass
    try: row = get(g["league"], g["id"])
    except Exception: row = None
    if started:
        if row and row["pred"]:
            out["pred"] = dict(row["pred"], locked=True, saved_at=row["updated_at"], status=row["status"], result=_result(row))
    elif fresh:
        out["pred"] = dict(fresh, locked=False, start_ts=int(d.timestamp()) if d else None)
    return out

def _result(row):
    if row["status"] == "PENDIENTE": return None
    return dict(ml=row["r_ml"], total=row["r_total"], spread=row["r_spread"], corners=row.get("r_corners"), score=row["r_score"], sets=row["r_sets"], score_text=row["score_text"], note=row["note"],
                final=[row["final_home"], row["final_away"]])

# ------------------------------------------------------------------ calificación con el marcador final real
def grade_row(row, res, now=None):
    """-> dict de columnas o None (sigue pendiente). Reusa la liquidación de grading.settle para total/hándicap."""
    from .grading import settle
    now = now or time.time()
    if res["state"] == "void": return dict(status="ANULADO", note=res.get("note"))
    if res["state"] != "final": return None
    p = row["pred"]; tennis = row["sport"] == "tenis"
    rr = res if tennis else dict(home=res["home"], away=res["away"], **({"home_t": res["home_t"], "away_t": res["away_t"]} if "home_t" in res else {}))
    h, a = res["home"], res["away"]
    out = dict(status="GRADED", final_home=h, final_away=a, note=res.get("note"))
    win = "home" if h > a else "away" if a > h else "draw"
    out["r_ml"] = "GANADO" if win == p["winner"]["side"] else "PERDIDO"
    if p.get("total") and not res.get("unsure_total"):
        out["r_total"] = settle("total", p["total"]["side"], p["total"]["line"], rr, three_way=(row["sport"] == "futbol"))
    if p.get("spread"):
        out["r_spread"] = settle("spread", p["spread"]["side"], (p["spread"]["line"] if p["spread"]["side"] == "home" else -p["spread"]["line"]), rr, three_way=(row["sport"] == "futbol"))
    if p.get("corners") and res.get("corners_total") is not None:
        out["r_corners"] = settle("total", p["corners"]["side"], p["corners"]["line"], dict(home=res["corners_total"], away=0))
    sc = p["score"]
    if tennis:
        ok = [list(x) for x in (res.get("sets") or [])] == sc.get("sets")
        out["r_score"] = "GANADO" if ok else "PERDIDO"
        out["r_sets"] = "GANADO" if (sc["home"], sc["away"]) == (h, a) else "PERDIDO"
        out["score_text"] = res.get("score_text")
    else:
        hh, aa = (res["home_t"], res["away_t"]) if False else (h, a)
        out["r_score"] = "GANADO" if (sc["home"], sc["away"]) == (hh, aa) else "PERDIDO"
        out["score_text"] = f"{h}-{a}"
    return out

def _pending(now):
    rows = _rows("SELECT * FROM predictions WHERE status='PENDIENTE' AND start_ts<=? ORDER BY start_ts LIMIT 500", (int(now),))
    for r in rows: r["pred"] = json.loads(r.pop("payload") or "null")
    return rows

def _write(rid, g, now):
    cols = {k: v for k, v in g.items()}; cols["graded_at"] = int(now)
    with history._lock:
        c = _c()
        c.execute(f"UPDATE predictions SET {','.join(k + '=?' for k in cols)} WHERE id=?", (*cols.values(), rid)); c.commit()

async def grade_pending(now=None):
    import asyncio
    from .grading import fetch_result
    now = now or time.time()
    rows = _pending(now)
    by = {}
    for r in rows: by.setdefault((r["league"], r["eid"]), []).append(r)
    sem = asyncio.Semaphore(6)
    async def one(rs):
        async with sem:
            try: return await fetch_result(rs[0])
            except Exception as ex: return dict(state="pending", note=str(ex)[:80])
    results = await asyncio.gather(*[one(rs) for rs in by.values()])
    for rs, res in zip(by.values(), results):
        if res.get("state") == "final" and any((r["pred"] or {}).get("corners") for r in rs):
            try:
                from .cache import get_json
                from .config import ESPN, LEAGUES
                c = corners_of(await get_json(f"{ESPN}/{LEAGUES[rs[0]['league']]['path']}/summary", ttl=60, params={"event": rs[0]["eid"]}))
                if c: res["corners_total"] = c["home"] + c["away"]
            except Exception: pass
    n = 0
    for rs, res in zip(by.values(), results):
        for r in rs:
            g = grade_row(r, res, now)
            if g: _write(r["id"], g, now); n += 1
    return dict(checked=len(by), graded=n)

# ------------------------------------------------------------------ récord de predicciones
def stats(sport=None, days=None):
    w, a = ["status='GRADED'"], []
    if sport: w.append("sport=?"); a.append(sport)
    if days: w.append("start_ts>=?"); a.append(int(time.time() - days * 86400))
    rows = _rows(f"SELECT * FROM predictions WHERE {' AND '.join(w)} ORDER BY start_ts DESC", tuple(a))
    def agg(col):
        W = sum(1 for r in rows if r[col] in ("GANADO", "MEDIO_GANADO")); L = sum(1 for r in rows if r[col] in ("PERDIDO", "MEDIO_PERDIDO")); P = sum(1 for r in rows if r[col] == "PUSH")
        return dict(hit=W, miss=L, push=P, n=W + L, pct=(W / (W + L) * 100 if W + L else None))
    pend = _rows("SELECT COUNT(*) n FROM predictions WHERE status='PENDIENTE'" + (" AND sport=?" if sport else ""), ((sport,) if sport else ()))[0]["n"]
    recent = []
    for r in rows[:12]:
        p = json.loads(r["payload"] or "null") or {}
        recent.append(dict(league=r["league"], eid=r["eid"], sport=r["sport"], home=r["home"], away=r["away"], start_ts=r["start_ts"], score_text=r["score_text"], pred=p.get("score"),
                           winner=(p.get("winner") or {}).get("side"), ml=r["r_ml"], total=r["r_total"], spread=r["r_spread"], corners=r["r_corners"], score=r["r_score"]))
    return dict(graded=len(rows), pending=pend, ml=agg("r_ml"), total=agg("r_total"), spread=agg("r_spread"), corners=agg("r_corners"), score=agg("r_score"), sets=agg("r_sets"), recent=recent)
