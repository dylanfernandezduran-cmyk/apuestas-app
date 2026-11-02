"""Lesiones (ESPN /injuries por liga) + seguimiento propio en SQLite para detectar 'regresa de lesión' de forma honesta:
sólo se afirma lo que vimos cambiar en el reporte (jugador sale del reporte / mejora de estado) desde que el servidor empezó a seguirlo."""
import re, time
from .cache import get_json
from .config import ESPN, LEAGUES
from . import history as H

OUT_KEYS = ("out", "injured reserve", "suspension", "ir", "pup", "nfi", "inactive", "out for season")
RANK = {"out": 3, "doubt": 2, "dtd": 1}
STATUS_ES = {"out": "Baja", "injured reserve": "Reserva de lesionados", "suspension": "Suspendido", "doubtful": "Dudoso", "questionable": "Cuestionable",
             "day-to-day": "Día a día", "probable": "Probable", "out for season": "Fuera de temporada", "inactive": "Inactivo"}
_last_track = {}

def bucket(status):
    s = (status or "").lower().strip()
    if s in ("active", "healthy"): return None
    if any(s == k or s.startswith(k) for k in OUT_KEYS): return "out"
    if "doubt" in s: return "doubt"
    return "dtd"

def status_es(status):
    return STATUS_ES.get((status or "").lower().strip(), status or "")

def _pid(a):
    """ESPN no trae athlete.id en /injuries: se toma del enlace de la ficha del jugador (…/id/4685503/nombre); respaldo: nombre."""
    if a.get("id"): return str(a["id"])
    for l in a.get("links") or []:
        m = re.search(r"/id/(\d+)", l.get("href") or "")
        if m: return m.group(1)
    return "n:" + re.sub(r"[^a-z]", "", (a.get("displayName") or "").lower())

def _entry(i):
    a = i.get("athlete") or {}; det = i.get("details") or {}
    clean = lambda x: x if x and str(x).lower() not in ("not specified", "unknown") else None
    detail = " · ".join(x for x in [clean(det.get("type")), clean(det.get("detail")), clean(det.get("side"))] if x) or None
    return dict(id=_pid(a), name=a.get("displayName"), pos=(a.get("position") or {}).get("abbreviation"), status=i.get("status"), status_es=status_es(i.get("status")),
                bucket=bucket(i.get("status")), detail=detail, location=clean(det.get("location")), ret=det.get("returnDate"), date=i.get("date"),
                note=((i.get("shortComment") or "")[:300] or None), headshot=(a.get("headshot") or {}).get("href"))

def parse_league(d):
    """-> {team_id: dict(name, entries)} (sin jugadores 'Active')."""
    out = {}
    for t in (d or {}).get("injuries") or []:
        es = [_entry(i) for i in t.get("injuries", [])]
        es = [e for e in es if e["bucket"]]
        out[str(t.get("id"))] = dict(name=t.get("displayName"), entries=es)
    return out

def counts(entries):
    c = dict(out=0, doubt=0, dtd=0)
    for e in entries:
        if e.get("bucket"): c[e["bucket"]] += 1
    return c

async def league_injuries(league):
    """-> (by_team, fetched_ts, supported). supported=False si ESPN no publica lesiones para la liga (p. ej. fútbol)."""
    cfg = LEAGUES[league]
    if cfg["family"] in ("tennis",): return {}, None, False
    d = await get_json(f"{ESPN}/{cfg['path']}/injuries", ttl=600)
    if d is None: return {}, None, False
    by = parse_league(d)
    supported = bool(d.get("injuries"))
    if supported:
        try: track(league, by)
        except Exception: pass
    return by, time.time(), supported

# ------------------------------------------------------------------ seguimiento (SQLite)
def _tables(c):
    c.execute("CREATE TABLE IF NOT EXISTS inj_cur(league TEXT, pid TEXT, team_id TEXT, name TEXT, pos TEXT, status TEXT, bucket TEXT, detail TEXT, since TEXT, seen INTEGER, PRIMARY KEY(league,pid))")
    c.execute("CREATE TABLE IF NOT EXISTS inj_events(league TEXT, pid TEXT, team_id TEXT, name TEXT, pos TEXT, ts INTEGER, kind TEXT, old TEXT, new TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_inj_ev ON inj_events(league, team_id, ts)")

def track(league, by_team, now=None):
    """Compara el reporte actual con el último visto y guarda eventos: nuevo · cambio (mejora/empeora) · salio. La primera vez sólo fija la línea base."""
    now = int(now or time.time())
    if now - _last_track.get(league, 0) < 240: return 0
    if len(by_team) < 5: return 0       # respuesta parcial: no se infiere nada
    c = H._open()
    if not c: return 0
    n = 0
    with H._lock:
        _tables(c)
        first = not c.execute("SELECT 1 FROM meta WHERE k=?", (f"inj_start_{league}",)).fetchone()
        cur = {r[0]: r for r in c.execute("SELECT pid,team_id,name,pos,status,bucket FROM inj_cur WHERE league=?", (league,))}
        seen = set()
        for tid, t in by_team.items():
            for e in t["entries"]:
                pid = e["id"]; seen.add(pid)
                old = cur.get(pid)
                if old is None:
                    c.execute("INSERT OR REPLACE INTO inj_cur VALUES(?,?,?,?,?,?,?,?,?,?)", (league, pid, tid, e["name"], e["pos"], e["status"], e["bucket"], e["detail"], e["date"], now))
                    if not first: c.execute("INSERT INTO inj_events VALUES(?,?,?,?,?,?,?,?,?)", (league, pid, tid, e["name"], e["pos"], now, "nuevo", None, e["status"])); n += 1
                else:
                    if old[5] != e["bucket"] or old[4] != e["status"] or old[1] != tid:
                        better = RANK.get(e["bucket"], 0) < RANK.get(old[5], 0)
                        kind = "mejora" if better else ("empeora" if RANK.get(e["bucket"], 0) > RANK.get(old[5], 0) else "cambio")
                        c.execute("INSERT INTO inj_events VALUES(?,?,?,?,?,?,?,?,?)", (league, pid, tid, e["name"], e["pos"], now, kind, old[4], e["status"])); n += 1
                    c.execute("UPDATE inj_cur SET team_id=?, name=?, pos=?, status=?, bucket=?, detail=?, since=?, seen=? WHERE league=? AND pid=?",
                              (tid, e["name"], e["pos"], e["status"], e["bucket"], e["detail"], e["date"], now, league, pid))
        for pid, old in cur.items():
            if pid not in seen:
                c.execute("INSERT INTO inj_events VALUES(?,?,?,?,?,?,?,?,?)", (league, pid, old[1], old[2], old[3], now, "salio", old[4], None))
                c.execute("DELETE FROM inj_cur WHERE league=? AND pid=?", (league, pid)); n += 1
        if first: c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (f"inj_start_{league}", str(now)))
        c.commit()
    _last_track[league] = now
    return n

def tracking_since(league):
    try:
        c = H._open()
        with H._lock:
            _tables(c)
            r = c.execute("SELECT v FROM meta WHERE k=?", (f"inj_start_{league}",)).fetchone()
        return int(r[0]) if r else None
    except Exception: return None

def returning(league, team_id, days=10, now=None):
    """Jugadores del equipo que salieron del reporte o mejoraron de estado en los últimos `days` días (según nuestro seguimiento)."""
    now = int(now or time.time())
    try:
        c = H._open()
        with H._lock:
            _tables(c)
            rows = c.execute("SELECT pid,name,pos,ts,kind,old,new FROM inj_events WHERE league=? AND team_id=? AND ts>=? AND kind IN ('salio','mejora') ORDER BY ts DESC",
                             (league, str(team_id), now - days * 86400)).fetchall()
            cur_ids = {r[0]: r[1] for r in c.execute("SELECT pid, team_id FROM inj_cur WHERE league=?", (league,))}
    except Exception:
        return []
    out, seen = [], set()
    for pid, name, pos, ts, kind, old, new in rows:
        if pid in seen: continue
        seen.add(pid)
        if kind == "salio" and pid in cur_ids: continue    # volvió a aparecer en el reporte (o en otro equipo): no es un regreso
        out.append(dict(id=pid, name=name, pos=pos, ts=ts, kind=kind, old=status_es(old), new=status_es(new) if new else None))
    return out

def team_payload(league, team_id, entries, key_ids=()):
    es = []
    for e in entries:
        e = dict(e); e["key"] = e["id"] in key_ids; es.append(e)
    es.sort(key=lambda e: (-RANK.get(e["bucket"], 0), not e["key"], e["name"] or ""))
    return dict(entries=es, counts=counts(es), returning=returning(league, team_id))
