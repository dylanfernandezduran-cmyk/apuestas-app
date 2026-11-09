"""Calificación de picks con marcadores FINALES reales (ESPN site API; MLB también vía ESPN). Nunca se inventa un resultado:
mientras la fuente no confirme el final, el pick sigue PENDIENTE.

Estados: GANADO · PERDIDO · PUSH (devolución) · MEDIO_GANADO / MEDIO_PERDIDO (líneas de cuarto, p. ej. -0.25, 2.75) · ANULADO (cancelado/WO/retiro/…)

Reglas por mercado (selection = home|away|draw|over|under|1X|X2|12; line = línea del lado elegido):
  ml      ganador del partido. Fútbol: 1X2 a 90 min (+descuento). Tenis: ganador del partido. Empate en deportes de 2 vías (NFL) = PUSH.
  dc      doble oportunidad (fútbol): 1X, X2, 12.
  btts    ambos anotan (fútbol, 90 min): yes|no.
  spread  hándicap/spread/run line/puck line: margen del lado + línea vs 0. Tenis: JUEGOS totales ganados por cada jugador (suma de los sets).
  total   over/under del total de puntos/carreras/goles. Tenis: total de JUEGOS.
  sspread / stotal (sólo tenis, sets): hándicap y total de SETS.
  Líneas de cuarto (x.25 / x.75): se parte la apuesta en dos medias líneas → medio ganado / medio perdido (o G/P completo si ambas coinciden).
Marcadores: tiempo extra cuenta en NBA/NFL/NHL/MLB. NHL: el gol decisivo de la tanda de penales NO cuenta para el total (sí para ML/puck line).
Fútbol: si hubo tiempo extra/penales (copas) se usa la suma de los dos tiempos (90'); si ESPN no la trae, queda PENDIENTE (no se adivina)."""
import asyncio, re, time
from .cache import get_json
from .config import ESPN, LEAGUES
from . import record as R

# --------------------------------------------------------------------- liquidación pura (sin red)
def _sign(v):
    return 1 if v > 1e-9 else (-1 if v < -1e-9 else 0)

def _split(line):
    """Línea de cuarto -> dos medias líneas; si no, [line]."""
    if round(line * 4) % 2 != 0: return [line - 0.25, line + 0.25]
    return [line]

def settle_line(value_fn, line):
    """value_fn(sub_line) -> margen ajustado (>0 gana). Devuelve fracción de resultado en {-1,-.5,0,.5,1}."""
    subs = _split(float(line))
    return sum(_sign(value_fn(s)) for s in subs) / len(subs)

def frac_to_status(f):
    return {1: "GANADO", 0.5: "MEDIO_GANADO", 0: "PUSH", -0.5: "MEDIO_PERDIDO", -1: "PERDIDO"}[f]

def settle(market, selection, line, res, three_way=False):
    """res: dict(home, away, [home_t, away_t para totales], [gh, ga, sh, sa para tenis]). Devuelve status (GANADO/PERDIDO/PUSH/MEDIO_*) o None si falta dato."""
    if market in ("spread", "total", "sspread", "stotal") and line is None and market != "ml": return None
    tennis = "gh" in res
    if market == "ml":
        h, a = res["home"], res["away"]
        if h is None or a is None: return None
        tie = "PERDIDO" if three_way else "PUSH"      # fútbol 1X2: el empate pierde apuestas a local/visitante; deportes de 2 vías (NFL): devolución
        if selection == "home": return "GANADO" if h > a else "PERDIDO" if h < a else tie
        if selection == "away": return "GANADO" if a > h else "PERDIDO" if a < h else tie
        if selection == "draw": return ("GANADO" if h == a else "PERDIDO") if three_way else None   # sólo fútbol: en otros deportes un 3-way a 60' no se puede calificar con el marcador final
        return None
    if market == "btts":                              # ambos anotan (fútbol, 90 min)
        h, a = res["home"], res["away"]
        if h is None or a is None or selection not in ("yes", "no"): return None
        return "GANADO" if ((h > 0 and a > 0) == (selection == "yes")) else "PERDIDO"
    if market == "dc":
        h, a = res["home"], res["away"]
        if selection == "1X": return "GANADO" if h >= a else "PERDIDO"
        if selection == "X2": return "GANADO" if a >= h else "PERDIDO"
        if selection == "12": return "GANADO" if h != a else "PERDIDO"
        return None
    if market == "spread":
        h, a = (res["gh"], res["ga"]) if tennis else (res["home"], res["away"])
    elif market == "sspread":
        if not tennis: return None
        h, a = res["sh"], res["sa"]
    elif market == "total":
        if tennis: tot = res["gh"] + res["ga"]
        else:
            ht, at = res.get("home_t", res["home"]), res.get("away_t", res["away"])
            tot = ht + at
    elif market == "stotal":
        if not tennis: return None
        tot = res["sh"] + res["sa"]
    else:
        return None
    if market in ("spread", "sspread"):
        if selection == "home": f = settle_line(lambda s: (h - a) + s, line)
        elif selection == "away": f = settle_line(lambda s: (a - h) + s, line)
        else: return None
    else:
        if selection == "over": f = settle_line(lambda s: tot - s, line)
        elif selection == "under": f = settle_line(lambda s: s - tot, line)
        else: return None
    return frac_to_status(f)

# --------------------------------------------------------------------- fuentes de resultado (ESPN)
VOID_NAMES = ("CANCEL", "FORFEIT", "ABANDON", "WALKOVER", "RETIRED", "DEFAULT", "NO_CONTEST")
HOLD_NAMES = ("POSTPONED", "SUSPENDED", "DELAYED", "RAIN", "IN_PROGRESS", "SCHEDULED", "HALFTIME", "END_PERIOD", "FIRST_HALF", "SECOND_HALF", "OVERTIME", "SHOOTOUT")

def _ival(x):
    if x is None: return None
    if isinstance(x, dict):
        x = x.get("value", x.get("displayValue"))
    try: return int(float(x))
    except Exception: return None

def parse_team_summary(summ, home_id=None, away_id=None, family=None):
    """Interpreta ESPN summary -> dict(state=final|void|pending, home, away, [home_t, away_t], score_text, note)."""
    try:
        comp = summ["header"]["competitions"][0]
        st = (comp.get("status") or {}).get("type") or summ["header"].get("status", {}).get("type", {}) or {}
        cs = comp["competitors"]
    except Exception:
        return dict(state="pending", note="Sin respuesta válida de la fuente")
    name, state, detail = (st.get("name") or ""), st.get("state"), (st.get("detail") or st.get("shortDetail") or "")
    if any(k in name for k in ("CANCEL", "FORFEIT", "ABANDON")):
        return dict(state="void", note=f"Juego anulado por la fuente ({detail or name})")
    if "POSTPONED" in name or "SUSPENDED" in name:
        return dict(state="pending", note=f"Juego pospuesto/suspendido ({detail or name}); sigue pendiente", postponed=True)
    if state != "post" or not st.get("completed", state == "post"):
        return dict(state="pending", note=None)
    def pick(side, tid):
        c = next((x for x in cs if tid and str(x["team"]["id"]) == str(tid)), None)
        return c or next((x for x in cs if x.get("homeAway") == side), None)
    H, A = pick("home", home_id), pick("away", away_id)
    if not H or not A or H is A: return dict(state="pending", note="No se pudo identificar a los equipos en la fuente")
    h, a = _ival(H.get("score")), _ival(A.get("score"))
    if h is None or a is None: return dict(state="pending", note="Marcador final no disponible")
    out = dict(state="final", home=h, away=a, note=None)
    ls = lambda c: [_ival(x) for x in (c.get("linescores") or [])]
    lh, la = ls(H), ls(A)
    if family == "soccer":
        if any(k in name for k in ("AET", "PEN", "EXTRA")) or "ET" in detail.split() or "Pen" in detail or "AET" in detail:
            if len(lh) >= 2 and len(la) >= 2 and None not in lh[:2] + la[:2]:
                out.update(home=sum(lh[:2]), away=sum(la[:2]), note="Tiempo extra/penales: se calificó con el marcador a 90' (suma de los dos tiempos)")
            else:
                return dict(state="pending", note="Hubo tiempo extra/penales y la fuente no trae el marcador a 90'; no se califica (no se adivina)")
    if family == "hockey" and detail.endswith("SO"):
        if len(lh) >= 5 and len(la) >= 5 and None not in lh + la:
            out.update(home_t=sum(lh[:4]), away_t=sum(la[:4]), note="Tanda de penales: el gol decisivo no cuenta para el total")
            out["so"] = True
        else:
            out["unsure_total"] = True
    return out

def parse_tennis_event(ev_comp, home_id, away_id):
    """ev_comp: competition de ESPN tenis. -> dict(state, home, away, gh, ga, sh, sa, sets, score_text, note)."""
    st = (ev_comp.get("status") or {}).get("type") or {}
    name, state = st.get("name") or "", st.get("state")
    if any(k in name for k in VOID_NAMES) or any(k in (st.get("detail") or "").upper() for k in ("RETIRED", "WALKOVER", "RETIRE", "W/O")):
        if state == "post":
            # retiro a media partida: el partido sí se jugó y hay ganador real -> el ML se califica con ese ganador; walkover (no se jugó) se anula
            if "WALKOVER" not in (name + " " + (st.get("detail") or "")).upper() and "W/O" not in (st.get("detail") or "").upper():
                cs = ev_comp.get("competitors", [])
                H = next((c for c in cs if str(c.get("id")) == str(home_id)), None)
                A = next((c for c in cs if str(c.get("id")) == str(away_id)), None)
                if H and A and bool(H.get("winner")) != bool(A.get("winner")):
                    sh = [_ival(x) for x in H.get("linescores", [])]; sa = [_ival(x) for x in A.get("linescores", [])]
                    return dict(state="retired", winner="home" if H.get("winner") else "away",
                                score_text=" ".join(f"{x}-{y}" for x, y in zip(sh, sa) if x is not None and y is not None) + " ret.",
                                note=f"Retiro ({st.get('detail') or name}): el ML se califica con el ganador real; los demás mercados se anulan")
            return dict(state="void", note=f"Partido sin final normal ({st.get('detail') or name}): las casas liquidan distinto; no se califica")
    if state != "post": return dict(state="pending", note=None)
    if name != "STATUS_FINAL": return dict(state="pending", note=f"Estado '{name}' no reconocido como final; sigue pendiente")
    cs = ev_comp.get("competitors", [])
    H = next((c for c in cs if str(c.get("id")) == str(home_id)), None)
    A = next((c for c in cs if str(c.get("id")) == str(away_id)), None)
    if not H or not A:
        # ESPN reutiliza el id del partido cuando un jugador se retira antes de jugar (entra lucky loser/alterno): el partido
        # registrado nunca se jugó -> se anula (las casas también anulan), en vez de quedar pendiente para siempre.
        return dict(state="void", note="El partido cambió de jugadores (baja antes de jugar / lucky loser): el pick registrado se anula")
    sh = [_ival(x) for x in H.get("linescores", [])]; sa = [_ival(x) for x in A.get("linescores", [])]
    if not sh or len(sh) != len(sa) or None in sh + sa: return dict(state="pending", note="Marcador por sets no disponible")
    if any(max(x, y) > 7 or max(x, y) < 6 for x, y in zip(sh, sa)):
        return dict(state="pending", note="Marcador de sets atípico (¿súper tie-break?); no se califica")
    swon_h = sum(1 for x, y in zip(sh, sa) if x > y); swon_a = sum(1 for x, y in zip(sh, sa) if y > x)
    if swon_h == swon_a or bool(H.get("winner")) != (swon_h > swon_a) or bool(A.get("winner")) != (swon_a > swon_h):
        return dict(state="pending", note="Marcador inconsistente con el ganador; no se califica")
    return dict(state="final", home=swon_h, away=swon_a, gh=sum(sh), ga=sum(sa), sh=swon_h, sa=swon_a, sets=list(zip(sh, sa)),
                score_text=" ".join(f"{x}-{y}" for x, y in zip(sh, sa)), note=None)

async def fetch_result(row):
    """Obtiene y normaliza el resultado de un pick (fila de BD)."""
    lg = row["league"]; cfg = LEAGUES.get(lg)
    if not cfg: return dict(state="pending", note="Liga desconocida")
    if cfg["family"] == "tennis":
        import datetime as _dt
        day = _dt.datetime.utcfromtimestamp(row["start_ts"]).strftime("%Y%m%d") if row.get("start_ts") else None
        got = False
        for params in (None, {"dates": day} if day else None):
            if params is None and got: continue
            d = await get_json(f"{ESPN}/{cfg['path']}/scoreboard", ttl=120, **({"params": params} if params else {}))
            if not d: continue
            got = True
            for e in d.get("events", []):
                for gr in e.get("groupings", []):
                    if "Singles" not in gr["grouping"]["displayName"]: continue
                    for c in gr["competitions"]:
                        if str(c.get("id")) == str(row["eid"]): return parse_tennis_event(c, row["home_id"], row["away_id"])
        if not got: return dict(state="pending", note="Fuente sin respuesta")
        return dict(state="pending", note="El partido ya no aparece en el marcador de ESPN; sin resultado confirmado")
    summ = await get_json(f"{ESPN}/{cfg['path']}/summary", ttl=60, params={"event": row["eid"]})
    if not summ: return dict(state="pending", note="Fuente sin respuesta")
    return parse_team_summary(summ, row["home_id"], row["away_id"], cfg["family"])

def grade_row(row, res, now=None):
    """Aplica un resultado normalizado a una fila. Devuelve (status, units, score_text, final_home, final_away, note) o None si sigue pendiente."""
    now = now or time.time()
    if res["state"] == "void":
        return ("ANULADO", None, None, None, None, res.get("note"))
    if res["state"] == "retired":
        txt = f"{res['score_text']} ({row['home']} vs {row['away']})"
        if row["market"] != "ml": return ("ANULADO", None, txt, None, None, res.get("note"))
        st = "GANADO" if row["selection"] == res["winner"] else "PERDIDO"
        return (st, R.profit(st, row["odds"]), txt, None, None, res.get("note"))
    if res["state"] != "final":
        if res.get("postponed") and now - row["start_ts"] > 7 * 86400:
            return ("ANULADO", None, None, None, None, "Pospuesto más de 7 días sin jugarse: anulado")
        return None
    mk = row["market"]
    if mk == "total" and res.get("unsure_total"):
        return None
    if row["sport"] == "tenis":
        rr = res
    else:
        rr = dict(home=res["home"], away=res["away"])
        if "home_t" in res: rr.update(home_t=res["home_t"], away_t=res["away_t"])
    st = settle(mk, row["selection"], row["line"], rr, three_way=(row["sport"] == "futbol"))
    if st is None: return None
    # marcador mostrado: local-visitante como en el título "visitante @ local"
    if row["sport"] == "tenis":
        txt = f"{res['score_text']} ({row['home']} vs {row['away']})"
    elif row["sport"] == "futbol":
        txt = score_line_futbol(row["home"], res["home"], res["away"], row["away"])    # fútbol: local primero
    else:
        txt = f"{row['away']} {res['away']} @ {row['home']} {res['home']}"
    note = res.get("note")
    return (st, R.profit(st, row["odds"]), txt, res["home"], res["away"], note)

def score_line_futbol(home, hs, as_, away):
    """Fútbol: el primer equipo es el local -> 'Local 2 - 1 Visitante' (el marcador sigue el orden de los equipos)."""
    return f"{home} {hs} - {as_} {away}"

async def grade_pending(now=None, limit=500):
    """Califica todo lo pendiente cuyo juego ya empezó. Agrupa por juego (una consulta por juego). Devuelve resumen."""
    now = now or time.time()
    R.activate_started(now)
    rows = R.pending(now, limit)
    by = {}
    for r in rows: by.setdefault((r["league"], r["eid"]), []).append(r)
    sem = asyncio.Semaphore(6)
    out = dict(checked=len(by), graded=0, void=0, still_pending=0)
    async def one(k, rs):
        async with sem:
            try: res = await fetch_result(rs[0])
            except Exception as ex: return dict(state="pending", note=f"Error al consultar: {str(ex)[:80]}")
        return res
    results = await asyncio.gather(*[one(k, rs) for k, rs in by.items()])
    for (k, rs), res in zip(by.items(), results):
        for r in rs:
            g = grade_row(r, res, now)
            if g is None:
                out["still_pending"] += 1
                if r["status"] == "PENDIENTE" and res.get("note") and res.get("note") != r.get("note"): R.set_note(r["id"], res["note"])
                continue
            if r["status"] == "ANULADO" and g[0] != "ANULADO":   # cancelado/invertido antes del inicio, calificado con el resultado real
                g = g[:5] + ("; ".join(x for x in (f"{'Invertido' if r.get('state') == 'INVERTIDO' else 'Cancelado'} antes del inicio; calificado con el resultado real a la línea registrada", g[5]) if x),)
            elif r["status"] == "ANULADO": g = g[:5] + (r.get("note") or g[5],)
            R.set_grade(r["id"], *g, now=now)
            out["void" if g[0] == "ANULADO" else "graded"] += 1
            if g[0] != "ANULADO":
                try: R.dedupe_market(r["league"], r["eid"], r["market"], now=now)
                except Exception: pass
    return out
