"""Alineaciones reales de ESPN (cuando ya están publicadas) o PROYECTADAS con datos reales del último juego (claramente rotuladas).
Cambios vs la foto anterior (SQLite): 'X entra por Y', bajas de último momento. Nunca se inventa."""
import json, time
from .cache import get_json
from .config import ESPN, LEAGUES
from . import history as H

def _ath(a, **extra):
    at = a.get("athlete") or a
    d = dict(id=str(at.get("id")), name=at.get("displayName") or at.get("shortName"), pos=(at.get("position") or a.get("position") or {}).get("abbreviation"), jersey=at.get("jersey") or a.get("jersey"))
    d.update(extra); return d

def starters_from_summary(summ, family, team_id):
    """-> dict(formation, players=[...], pitcher=?, goalie=?) para un equipo, o None si ESPN aún no publica titulares."""
    team_id = str(team_id)
    if family == "soccer":
        for r in summ.get("rosters") or []:
            if str((r.get("team") or {}).get("id")) != team_id: continue
            st = [a for a in (r.get("roster") or []) if a.get("starter")]
            if len(st) < 9: return None
            return dict(formation=r.get("formation"), players=[_ath(a) for a in st])
        return None
    for t in (summ.get("boxscore") or {}).get("players") or []:
        if str((t.get("team") or {}).get("id")) != team_id: continue
        groups = t.get("statistics") or []
        if family == "basketball":
            ath = (groups[0].get("athletes") if groups else None) or []
            st = [a for a in ath if a.get("starter")]
            if len(st) < 5: return None
            return dict(players=[_ath(a) for a in st[:5]])
        if family == "baseball":
            bat = next((g for g in groups if g.get("type") == "batting" or g.get("name") == "batting"), None)
            ath = [a for a in ((bat or {}).get("athletes") or []) if a.get("batOrder") and a.get("starter")]
            if len(ath) < 8: return None
            ath.sort(key=lambda a: a["batOrder"])
            return dict(players=[_ath(a, order=a["batOrder"]) for a in ath])
        if family == "hockey":
            g = next((g for g in groups if (g.get("type") or g.get("name")) == "goalies"), None)
            ath = (g or {}).get("athletes") or []
            if not ath: return None
            starter = next((a for a in ath if a.get("starter")), ath[0])
            return dict(goalie=_ath(starter), players=[])
    return None

def probable_pitcher(summ, team_id):
    """Abridor probable de MLB (competitors[].probables del header)."""
    for c in (summ.get("header") or {}).get("competitions", [{}])[0].get("competitors", []):
        if str(c["team"]["id"]) == str(team_id):
            for p in c.get("probables") or []:
                a = p.get("athlete") or {}
                if a.get("displayName"):
                    st = {s.get("name"): s.get("displayValue") for s in p.get("statistics", [])}
                    return dict(id=str(a.get("id")), name=a["displayName"], pos="P", hand=None,
                                line=" · ".join(x for x in [f"{st.get('wins')}-{st.get('losses')}" if st.get("wins") is not None else None, f"ERA {st['ERA']}" if st.get("ERA") else None] if x) or None)
    return None

# ------------------------------------------------------------------ proyección a partir del último juego del equipo
async def last_game_starters(league, family, team_id, recent):
    """Titulares del último juego terminado del equipo (datos reales de ESPN). -> (starters, date, eid) o (None, None, None)."""
    path = LEAGUES[league]["path"]
    for r in (recent or [])[:2]:
        eid = r.get("id")
        if not eid: continue
        s = await get_json(f"{ESPN}/{path}/summary", ttl=6 * 3600, params={"event": eid})
        if not s: continue
        st = starters_from_summary(s, family, team_id)
        if st: return st, r.get("date"), eid
    return None, None, None

# ------------------------------------------------------------------ NFL: depth chart
async def depth_chart(league, team_id):
    d = await get_json(f"{ESPN}/{LEAGUES[league]['path']}/teams/{team_id}/depthcharts", ttl=6 * 3600)
    out = []
    if not d: return out
    for f in d.get("depthchart", []):
        if f.get("name") == "Special Teams":
            side = "ST"
        elif any(k in f.get("positions", {}) for k in ("qb",)):
            side = "ATAQUE"
        else:
            side = "DEFENSA"
        if side == "ST": continue
        pl = []
        for pos, v in f.get("positions", {}).items():
            ath = (v.get("athletes") or [])
            if not ath: continue
            a = ath[0]
            inj = a.get("injuries") or []
            pl.append(dict(pos=pos.upper(), id=str(a.get("id")), name=a.get("displayName"), inj=(inj[0].get("status") if inj and isinstance(inj[0], dict) else None),
                           backup=(ath[1].get("displayName") if len(ath) > 1 else None)))
        out.append(dict(side=side, name=f.get("name"), players=pl))
    return out

# ------------------------------------------------------------------ cambios (SQLite)
def diff(old, new):
    """old/new: listas de jugadores [{id,name,pos}] -> lista de textos 'Cambio: X entra por Y' / 'X sale del once'."""
    oi = {p["id"]: p for p in old or []}; ni = {p["id"]: p for p in new or []}
    ins = [p for i, p in ni.items() if i not in oi]; outs = [p for i, p in oi.items() if i not in ni]
    ch = []
    # empareja por posición cuando se puede; el resto por orden
    outs2 = list(outs)
    for p in ins:
        m = next((o for o in outs2 if o.get("pos") and o["pos"] == p.get("pos")), None) or (outs2[0] if outs2 else None)
        if m: outs2.remove(m)
        ch.append(dict(kind="cambio", enters=p["name"], leaves=(m or {}).get("name"), pos=p.get("pos")))
    for o in outs2: ch.append(dict(kind="sale", enters=None, leaves=o["name"], pos=o.get("pos")))
    return ch

def _tables(c):
    c.execute("CREATE TABLE IF NOT EXISTS lineup_snap(league TEXT, eid TEXT, team_id TEXT, ts INTEGER, status TEXT, players TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_lsnap ON lineup_snap(league, eid, team_id, ts)")

def track(league, eid, team_id, status, players, now=None):
    """Guarda la foto si cambió; devuelve cambios vs la anterior (lista) y el ts de la foto previa. Sin fotos previas -> ([], None)."""
    now = int(now or time.time())
    key = json.dumps(sorted(p["id"] for p in players))
    try:
        c = H._open()
        if not c: return [], None
        with H._lock:
            _tables(c)
            rows = c.execute("SELECT ts,status,players FROM lineup_snap WHERE league=? AND eid=? AND team_id=? ORDER BY ts DESC", (league, str(eid), str(team_id))).fetchall()
            last = rows[0] if rows else None
            lastp = json.loads(last[2]) if last else None
            if last and json.dumps(sorted(p["id"] for p in lastp)) == key:
                if last[1] != status: c.execute("INSERT INTO lineup_snap VALUES(?,?,?,?,?,?)", (league, str(eid), str(team_id), now, status, json.dumps(players))); c.commit()
            else:
                c.execute("INSERT INTO lineup_snap VALUES(?,?,?,?,?,?)", (league, str(eid), str(team_id), now, status, json.dumps(players))); c.commit()
            # cambios = diferencia de la primera foto OFICIAL-previa (o proyectada) vs la actual
            hist = [(r[0], r[1], json.loads(r[2])) for r in rows]
        if not hist: return [], None
        # compara contra la foto más reciente que sea distinta a la actual
        for ts, st, pl in hist:
            if json.dumps(sorted(p["id"] for p in pl)) != key:
                return [dict(c, vs=st) for c in diff(pl, players)], ts
        return [], None
    except Exception:
        return [], None
