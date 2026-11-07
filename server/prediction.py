"""Predicción NRNM: marcador proyectado + ganador + total + hándicap, DERIVADOS de las proyecciones del modelo (nada inventado).
Marcador exacto (pt84u): el escenario CONDICIONADO más probable que cumple, a la vez, ganador + total + hándicap del propio juego (los picks PICK/LEAN fijan lado y línea;
sin pick, la línea de mercado o la del modelo). Si no cabe todo, se sueltan primero las líneas derivadas del modelo y nunca un pick; la salida jamás se contradice
(si una línea choca con el marcador se corrige y queda en `adjusted`, con `aligned` = pick|marcador).
 · Fútbol: matriz de Poisson de goles -> marcador de mayor probabilidad dentro de la región factible (ej.: Más de 3.5 => ≥4 goles, Menos de 2.5 => ≤2).
 · NBA/NFL/NHL/MLB: margen y total del modelo -> marcador de mayor probabilidad (normal bivariada) dentro de la región factible.
 · Tenis: modelo de sets/juegos -> sets más probables y, dentro de ellos, el set por set más cercano a la media condicionada (juegos totales y hándicap coherentes), no la moda 6-4 6-4.
Se guarda ANTES de que empiece el juego (se actualiza mientras no haya empezado) y se bloquea al inicio.
Se califica con el marcador final real (mismas reglas de grading.py) en una tabla aparte `predictions` y su propio récord de aciertos."""
import itertools, json, math, time
from . import history, record as REC
from .odds import norm_cdf
from .model import pois_pmf, cover_normal, cover_matrix

PT = ("ml", "total", "spread", "score")     # tipos de acierto: ganador, total, hándicap, marcador exacto

# ------------------------------------------------------------------ construcción
# El marcador exacto se elige DENTRO de la región que cumple las líneas del propio juego (ganador, total, hándicap; y los picks del modelo si los hay),
# con la probabilidad real de cada marcador (Poisson / normal / sets-juegos). Si las líneas se contradicen entre sí, se descarta la de menor prioridad
# y esa línea se corrige para que SIEMPRE concuerde con el marcador mostrado (nunca hay salidas contradictorias).
def _ok(c, h, a):
    k, s, L = c
    if k == "w": return h == a if s == "draw" else ((h > a) if s == "home" else (a > h))
    if k == "t": return (h + a > L) if s == "over" else (h + a < L)
    if k == "b": return (h > 0 and a > 0) == (s == "yes")       # ambos anotan
    d = h - a + L                                   # hándicap: L = línea del LOCAL
    return d > 0 if s == "home" else d < 0

def _cascade(cons):
    """Subconjuntos de restricciones por prioridad lexicográfica: primero los que conservan la 1ª (picks del modelo, luego ganador, total, hándicap), etc."""
    cs = list(cons)
    for inc in itertools.product((True, False), repeat=len(cs)):
        yield [c for c, k in zip(cs, inc) if k]

def _soccer(mdl, odds, g):
    lh, la = mdl["lam_home"], mdl["lam_away"]
    ph, pa = pois_pmf(lh), pois_pmf(la)
    mat = [[a * b for b in pa] for a in ph]; tot = sum(map(sum, mat)); mat = [[x / tot for x in r] for r in mat]
    p = dict(home=mdl["p_home"], draw=mdl["p_draw"], away=mdl["p_away"])
    w = max(p, key=p.get)
    N = len(mat)
    def choose(cons):
        for cs in _cascade(cons):
            cells = [(i, j) for i in range(N) for j in range(N) if all(_ok(c, i, j) for c in cs)]
            if cells:
                h, a = max(cells, key=lambda x: mat[x[0]][x[1]])
                return dict(home=h, away=a, p=mat[h][a], p_cond=mat[h][a] / sum(mat[i][j] for i, j in cells)), cs
        return None, []
    out = dict(kind="poisson", winner=dict(side=w, p=p[w], probs=p), proj=dict(home=lh, away=la, total=lh + la, margin=lh - la))
    return out, mdl["total"], mdl["cover"], choose

def _pmass(x, mu, sg): return norm_cdf((x + .5 - mu) / sg) - norm_cdf((x - .5 - mu) / sg)

def _margin(mdl, odds, g):
    T, mu, sg, ts = mdl["exp_total"], mdl["mu"], mdl["sigma"], mdl["tsigma"]
    hp, ap = (T + mu) / 2, (T - mu) / 2
    h0, a0 = max(0, int(round(hp))), max(0, int(round(ap)))
    w = "home" if mu >= 0 else "away"
    def choose(cons):
        for cs in _cascade(cons):
            best = None; R = 14
            for h in range(max(0, h0 - R), h0 + R + 1):
                for a in range(max(0, a0 - R), a0 + R + 1):
                    if h == a or not all(_ok(c, h, a) for c in cs): continue
                    pr = 2 * _pmass(h - a, mu, sg) * _pmass(h + a, T, ts)
                    if best is None or pr > best[0]: best = (pr, h, a)
            if best: return dict(home=best[1], away=best[2], p=best[0]), cs
        return None, []
    p = dict(home=mdl["p_home"], away=mdl["p_away"])
    out = dict(kind="margen", winner=dict(side=w, p=p[w], probs=p), proj=dict(home=hp, away=ap, total=T, margin=mu))
    return out, mdl["total"], mdl["cover"], choose

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
    eg = sum((k[2] + k[3]) * v for k, v in dist.items()); em = sum((k[2] - k[3]) * v for k, v in dist.items())
    def seqs(win, nw, nl):
        """Secuencias set a set (juegos local, juegos visita) para un resultado de sets; p = producto real de P(marcador de set) (sets i.i.d.)."""
        wsc = [k for k in sd if (k[0] > k[1]) == (win == "home")]; lsc = [k for k in sd if (k[0] > k[1]) != (win == "home")]
        order = ["w"] * nw if nl == 0 else (["w", "l"] * 6)[:nw + nl - 1] + ["w"]      # con perdedor ganando sets intermedios (patrón habitual)
        pools = [wsc if o == "w" else lsc for o in order]
        for combo in itertools.product(*pools):
            pr = 1.0
            for c in combo: pr *= sd[c]
            yield combo, pr
    def choose(cons, win):
        """Resultado de sets con más masa DENTRO de las líneas (total/hándicap de juegos) y, dentro de él, la secuencia set a set más probable que las cumple."""
        gc = [c for c in cons if c[0] != "w"]
        for cs in _cascade(gc):
            mass = {}
            for (sa, sb, ga, gb), v in dist.items():
                if (sa > sb) == (win == "home") and all(_ok(c, ga, gb) for c in cs): mass[(sa, sb)] = mass.get((sa, sb), 0) + v
            if not mass: continue
            tot_w = sum(v for (sa, sb, _, _), v in dist.items() if (sa > sb) == (win == "home"))
            res = max(mass, key=mass.get)
            nw, nl = (res if win == "home" else res[::-1])
            # media condicional (juegos del ganador / del perdedor) del resultado elegido dentro de las líneas: se muestra la secuencia set a set factible MÁS CERCANA
            # a esa media (marcador representativo, no el pico artificial 6-4 6-4); empate -> la más probable
            sel = [(k, v) for k, v in dist.items() if (k[0], k[1]) == res and all(_ok(c, k[2], k[3]) for c in cs)]
            zt = sum(v for _, v in sel)
            mh = sum(k[2] * v for k, v in sel) / zt; ma = sum(k[3] * v for k, v in sel) / zt
            best = None
            for combo, pr in seqs(win, nw, nl):
                gh = sum(x[0] for x in combo); ga = sum(x[1] for x in combo)
                if not all(_ok(c, gh, ga) for c in cs): continue
                key = ((gh - mh) ** 2 + (ga - ma) ** 2, -pr)
                if best is None or key < best[0]: best = (key, combo, gh, ga, pr)
            if not best: continue
            _, combo, gh, ga, pr = best
            return dict(home=res[0], away=res[1], p=mass[res], p_cond=mass[res] / (sum(mass.values()) or 1), sets=[list(c) for c in combo], p_seq=pr, games=[gh, ga]), cs
        return None, []
    out = dict(kind="tenis", winner=dict(side=w, p=max(pm, 1 - pm), probs=dict(home=pm, away=1 - pm)),
               proj=dict(total=eg, margin=em, pg=pg, best_of=bo))
    def total(t):
        win = sum(v for k, v in dist.items() if k[2] + k[3] > t); loss = sum(v for k, v in dist.items() if k[2] + k[3] < t)
        z = win + loss; return (win / z, loss / z, 1 - z) if z else (.5, .5, 0)
    def cover(t):
        win = sum(v for k, v in dist.items() if (k[2] - k[3]) > t); loss = sum(v for k, v in dist.items() if (k[2] - k[3]) < t)
        z = win + loss; return (win / z, loss / z, 1 - z) if z else (.5, .5, 0)
    return out, total, cover, (lambda cons: choose(cons, next((c[1] for c in cons if c[0] == "w"), w)))

def _pick_cons(picks):
    """Picks accionables del propio juego (PICK o el lean si es LEAN/PICK) -> {mercado: (lado, línea propia)}; el mejor edge de cada mercado."""
    if not picks: return {}
    cands = list(picks.get("candidates") or [])
    ok = [c for c in cands if c.get("status") == "PICK"]
    lean = picks.get("lean")
    if lean and picks.get("status") in ("PICK", "LEAN") and lean not in ok: ok.append(lean)
    out = {}
    for c in ok:
        mk = c.get("market")
        if mk in out or mk not in ("ML", "Spread", "Total", "BTTS"): continue
        if c.get("side") in ("home", "away", "draw", "over", "under", "yes", "no"): out[mk] = (c["side"], c.get("line"))
    return out

def build(game, mdl, odds, fam, corners=None, picks=None):
    """Predicción para un juego PRE o None si no hay modelo suficiente. corners: salida de corners_info() (sólo fútbol, datos reales de ESPN).
    picks: dict(lean, status, candidates) del propio juego: ganador/total/hándicap y el marcador exacto se alinean con ellos (sin contradicciones)."""
    if not mdl: return None
    try:
        if fam == "tennis": out, total, cover, choose = _tennis(mdl, odds, game)
        elif fam == "soccer": out, total, cover, choose = _soccer(mdl, odds, game)
        else: out, total, cover, choose = _margin(mdl, odds, game)
    except Exception:
        return None
    if not out: return None
    pk = _pick_cons(picks)
    fixed = set()                              # líneas que siguen a un pick del modelo (prioridad alta para el marcador)
    # ganador: sigue al pick ML si lo hay
    if "ML" in pk and pk["ML"][0] in out["winner"]["probs"]:
        sd_ = pk["ML"][0]
        if sd_ != out["winner"]["side"]: out["winner"]["side"] = sd_; out["winner"]["p"] = out["winner"]["probs"][sd_]; out["winner"]["aligned"] = "pick"
        fixed.add("w")
    tt = (odds or {}).get("total") or {}
    T, src = None, None
    if "Total" in pk and pk["Total"][1] is not None: T, src = pk["Total"][1], "mercado"
    elif "over" in tt and tt["over"].get("line") is not None and (tt["over"]["line"] * 4) % 2 == 0: T, src = tt["over"]["line"], "mercado"
    elif fam == "soccer": T, src = 2.5, "modelo"          # sin línea de mercado: la línea estándar de fútbol (2.5), marcada como del modelo
    elif fam == "tennis": T, src = math.floor(out["proj"]["total"]) + .5, "modelo"   # sin línea de mercado: mediana del modelo de juegos totales
    if T is not None:
        w, l, _ = total(T)
        side = ("over" if w >= l else "under") if "Total" not in pk else pk["Total"][0]
        out["total"] = dict(line=T, line_src=src, side=side, p=(w if side == "over" else l), p_over=w, proj=out["proj"].get("total"), label=f"{'Más' if side == 'over' else 'Menos'} de {T:g}")
        if "Total" in pk: out["total"]["aligned"] = "pick"; fixed.add("t")
    sp = (odds or {}).get("spread") or {}
    SL = None
    if "Spread" in pk and pk["Spread"][1] is not None: SL = pk["Spread"][1] if pk["Spread"][0] == "home" else -pk["Spread"][1]; ssrc = "mercado"
    elif "home" in sp and sp["home"].get("line") is not None and (sp["home"]["line"] * 4) % 2 == 0: SL = sp["home"]["line"]; ssrc = "mercado"
    if SL is not None and (SL * 4) % 2 == 0:
        ph, pa = cover(-SL)[0], cover(-SL)[1]
        side = ("home" if ph >= pa else "away") if "Spread" not in pk else pk["Spread"][0]
        out["spread"] = dict(line=SL, line_src=ssrc, side=side, p=(ph if side == "home" else pa), p_home=ph, p_away=pa, proj=out["proj"].get("margin"))
        if "Spread" in pk: out["spread"]["aligned"] = "pick"; fixed.add("s")
    elif fam == "soccer":
        # sin hándicap de mercado: el hándicap más exigente (−1.5 / −0.5) que el ganador pronosticado cubre con ≥50% según el modelo (línea del modelo)
        w = out["winner"]["side"]
        if w in ("home", "away"):
            for Lw in (1.5, 0.5):
                L = -Lw if w == "home" else Lw          # línea del LOCAL
                pc = cover(-L)[0] if w == "home" else cover(-L)[1]
                if pc >= 0.5:
                    out["spread"] = dict(line=L, line_src="modelo", side=w, p=pc, p_home=cover(-L)[0], p_away=cover(-L)[1], proj=out["proj"].get("margin")); break
    # --- ambos anotan (fútbol): prob. del modelo = masa de la matriz de Poisson con goles de los dos; sigue al pick BTTS si lo hay
    if fam == "soccer" and mdl.get("p_btts") is not None:
        py = mdl["p_btts"]; bo = (odds or {}).get("btts") or {}
        side = ("yes" if py >= .5 else "no") if "BTTS" not in pk else pk["BTTS"][0]
        out["btts"] = dict(side=side, p=(py if side == "yes" else 1 - py), p_yes=py, price=bo.get(side), book=("DraftKings" if bo else None),
                           label=f"Ambos anotan: {'Sí' if side == 'yes' else 'No'}")
        if "BTTS" in pk: out["btts"]["aligned"] = "pick"; fixed.add("b")
    # --- marcador exacto: el más probable que cumple TODAS las líneas (picks primero, luego las del modelo)
    cons = []
    if "w" in fixed: cons.append(("w", out["winner"]["side"], None))
    if "t" in fixed: cons.append(("t", out["total"]["side"], out["total"]["line"]))
    if "s" in fixed: cons.append(("s", out["spread"]["side"], out["spread"]["line"]))
    if "b" in fixed: cons.append(("b", out["btts"]["side"], None))
    if "w" not in fixed: cons.append(("w", out["winner"]["side"], None))
    if "t" not in fixed and out.get("total"): cons.append(("t", out["total"]["side"], out["total"]["line"]))
    if "s" not in fixed and out.get("spread"): cons.append(("s", out["spread"]["side"], out["spread"]["line"]))
    if "b" not in fixed and out.get("btts"): cons.append(("b", out["btts"]["side"], None))
    sc, kept = choose(cons)
    if not sc: return None
    out["score"] = sc
    # --- coherencia final: toda línea descartada se corrige para concordar con el marcador mostrado
    h, a = (sc["games"] if fam == "tennis" else (sc["home"], sc["away"]))
    res_side = ("home" if sc["home"] > sc["away"] else "away" if sc["away"] > sc["home"] else "draw")
    notes = []
    if res_side != out["winner"]["side"]:
        out["winner"]["side"] = res_side; out["winner"]["p"] = out["winner"]["probs"].get(res_side, 0); out["winner"]["aligned"] = "marcador"; notes.append("winner")
    t = out.get("total")
    if t and not _ok(("t", t["side"], t["line"]), h, a) and h + a != t["line"]:
        t["side"] = "over" if h + a > t["line"] else "under"; t["p"] = t["p_over"] if t["side"] == "over" else 1 - t["p_over"]; t["aligned"] = "marcador"
        t["label"] = f"{'Más' if t['side'] == 'over' else 'Menos'} de {t['line']:g}"; notes.append("total")
    s_ = out.get("spread")
    if s_ and not _ok(("s", s_["side"], s_["line"]), h, a) and h - a + s_["line"] != 0:
        s_["side"] = "home" if h - a + s_["line"] > 0 else "away"; s_["p"] = s_["p_home"] if s_["side"] == "home" else s_["p_away"]; s_["aligned"] = "marcador"; notes.append("spread")
    b_ = out.get("btts")
    if b_ and not _ok(("b", b_["side"], None), h, a):
        b_["side"] = "yes" if (h > 0 and a > 0) else "no"; b_["p"] = b_["p_yes"] if b_["side"] == "yes" else 1 - b_["p_yes"]; b_["aligned"] = "marcador"
        b_["price"] = ((odds or {}).get("btts") or {}).get(b_["side"]); b_["label"] = f"Ambos anotan: {'Sí' if b_['side'] == 'yes' else 'No'}"; notes.append("btts")
    if notes: out["adjusted"] = notes
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
    for col in ("r_corners", "r_btts"):
        try: c.execute(f"ALTER TABLE predictions ADD COLUMN {col} TEXT")
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
    return dict(ml=row["r_ml"], total=row["r_total"], spread=row["r_spread"], corners=row.get("r_corners"), btts=row.get("r_btts"), score=row["r_score"], sets=row["r_sets"], score_text=row["score_text"], note=row["note"],
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
    if p.get("btts") and not tennis:
        out["r_btts"] = settle("btts", p["btts"]["side"], None, rr)
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
                           winner=(p.get("winner") or {}).get("side"), ml=r["r_ml"], total=r["r_total"], spread=r["r_spread"], corners=r["r_corners"], btts=r.get("r_btts"), score=r["r_score"]))
    return dict(graded=len(rows), pending=pend, ml=agg("r_ml"), total=agg("r_total"), spread=agg("r_spread"), corners=agg("r_corners"), btts=agg("r_btts"), score=agg("r_score"), sets=agg("r_sets"), recent=recent)
