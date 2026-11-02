"""Historial propio de líneas y % de apuestas en SQLite (sólo guarda cambios, así crece poco).
Ruta: variable APUESTAS_DB, o <repo>/data/history.db (si no se puede escribir, carpeta temporal del sistema)."""
import os, sqlite3, threading, time, tempfile

_lock = threading.Lock()
_conn = None
_last_line = {}    # (league,eid,book,market,side) -> (line, price)
_last_split = {}   # (league,eid,market,side) -> (tickets, money)
PATH = None

def _open():
    global _conn, PATH
    if _conn: return _conn
    cands = []
    if os.environ.get("APUESTAS_DB"): cands.append(os.environ["APUESTAS_DB"])
    cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "history.db"))
    cands.append(os.path.join(tempfile.gettempdir(), "apuestas_history.db"))
    for p in cands:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
            c = sqlite3.connect(p, check_same_thread=False)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("CREATE TABLE IF NOT EXISTS lines(league TEXT, eid TEXT, ts INTEGER, book TEXT, market TEXT, side TEXT, line REAL, price INTEGER)")
            c.execute("CREATE INDEX IF NOT EXISTS ix_lines ON lines(league, eid, market)")
            c.execute("CREATE TABLE IF NOT EXISTS splits(league TEXT, eid TEXT, ts INTEGER, market TEXT, side TEXT, tickets INTEGER, money INTEGER)")
            c.execute("CREATE INDEX IF NOT EXISTS ix_splits ON splits(league, eid, market)")
            c.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
            if not c.execute("SELECT 1 FROM meta WHERE k='tennis_games_v1'").fetchone():
                # antes del fix, spread/total de tenis guardaban SETS (±1.5 / 2.5) bajo el mismo nombre que ahora usa JUEGOS: se descartan para no mezclar unidades
                c.execute("DELETE FROM lines WHERE league IN ('atp','wta') AND market IN ('spread','total')")
                c.execute("INSERT INTO meta VALUES('tennis_games_v1', ?)", (str(int(time.time())),))
            c.commit()
            for r in c.execute("SELECT l.league,l.eid,l.book,l.market,l.side,l.line,l.price FROM lines l JOIN (SELECT league,eid,book,market,side,MAX(ts) m FROM lines GROUP BY 1,2,3,4,5) x "
                               "ON l.league=x.league AND l.eid=x.eid AND l.book=x.book AND l.market=x.market AND l.side=x.side AND l.ts=x.m"):
                _last_line[tuple(r[:5])] = (r[5], r[6])
            for r in c.execute("SELECT s.league,s.eid,s.market,s.side,s.tickets,s.money FROM splits s JOIN (SELECT league,eid,market,side,MAX(ts) m FROM splits GROUP BY 1,2,3,4) x "
                               "ON s.league=x.league AND s.eid=x.eid AND s.market=x.market AND s.side=x.side AND s.ts=x.m"):
                _last_split[tuple(r[:4])] = (r[4], r[5])
            _conn = c; PATH = p
            return c
        except Exception:
            continue
    return None

def record(league, eid, books, splits, ts=None):
    """books: lista de dicts {id,name,ml,spread,total}; splits: {market:{side:{t,m}}}. Inserta sólo si cambió."""
    ts = int(ts or time.time())
    with _lock:
        c = _open()
        if not c: return 0
        rows_l, rows_s = [], []
        for b in books:
            bid = b["id"]
            for side in ("home", "away", "draw"):
                v = (b.get("ml") or {}).get(side)
                if v is not None: rows_l.append((league, eid, bid, "ml", side, None, v))
            for mk_, key_ in (("spread", "spread"), ("sspread", "sspread")):
                for side in ("home", "away"):
                    v = (b.get(key_) or {}).get(side)
                    if v: rows_l.append((league, eid, bid, mk_, side, v["line"], v["price"]))
            for mk_, key_ in (("total", "total"), ("stotal", "stotal")):
                for side in ("over", "under"):
                    v = (b.get(key_) or {}).get(side)
                    if v: rows_l.append((league, eid, bid, mk_, side, v["line"], v["price"]))
        ins_l = []
        for r in rows_l:
            k = tuple(r[:5]); val = (r[5], r[6])
            if _last_line.get(k) != val:
                _last_line[k] = val; ins_l.append((r[0], r[1], ts) + tuple(r[2:]))
        for mk, d in (splits or {}).items():
            for side, v in d.items():
                if v.get("t") is None and v.get("m") is None: continue
                k = (league, eid, mk, side); val = (v.get("t"), v.get("m"))
                if _last_split.get(k) != val:
                    _last_split[k] = val; rows_s.append((league, eid, ts, mk, side, val[0], val[1]))
        if ins_l: c.executemany("INSERT INTO lines VALUES (?,?,?,?,?,?,?,?)", ins_l)
        if rows_s: c.executemany("INSERT INTO splits VALUES (?,?,?,?,?,?,?)", rows_s)
        if ins_l or rows_s: c.commit()
        return len(ins_l) + len(rows_s)

def series(league, eid):
    with _lock:
        c = _open()
        if not c: return dict(lines={}, splits={}, first_ts=None, n_points=0)
        lines = {}; n = 0; first = None
        for book, mk, side, line, price, ts in c.execute("SELECT book,market,side,line,price,ts FROM lines WHERE league=? AND eid=? ORDER BY ts", (league, eid)):
            lines.setdefault(mk, {}).setdefault(book, {}).setdefault(side, []).append([ts, line, price]); n += 1
            first = ts if first is None else min(first, ts)
        spl = {}
        for mk, side, t, m, ts in c.execute("SELECT market,side,tickets,money,ts FROM splits WHERE league=? AND eid=? ORDER BY ts", (league, eid)):
            spl.setdefault(mk, {}).setdefault(side, []).append([ts, t, m]); n += 1
            first = ts if first is None else min(first, ts)
        return dict(lines=lines, splits=spl, first_ts=first, n_points=n)

def stats():
    with _lock:
        c = _open()
        if not c: return dict(path=None)
        return dict(path=os.path.abspath(PATH), lines=c.execute("SELECT COUNT(*) FROM lines").fetchone()[0],
                    splits=c.execute("SELECT COUNT(*) FROM splits").fetchone()[0], games=c.execute("SELECT COUNT(DISTINCT league||eid) FROM lines").fetchone()[0])
