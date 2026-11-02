"""En vivo: estado/reloj/periodo/situación (ESPN scoreboard + summary) y calificación PROVISIONAL de picks (sólo con el marcador actual).
Todo viene de ESPN; si un dato no existe se omite (nunca se inventa)."""
import re
from .grading import settle, _ival

def _lab(family, league, n):
    if family == "hockey": return "OT" if n > 3 else f"P{n}"
    if family == "basketball": return "OT" if n > 4 else f"Q{n}"
    if family == "football": return "OT" if n > 4 else f"Q{n}"
    return str(n)

def status_es(family, league, comp_status):
    """Texto corto de estado en español: 'Q3 5:32', 'Alta 5ª', "67'", 'Descanso', 'Final'."""
    st = (comp_status or {}).get("type") or {}
    state, name = st.get("state"), st.get("name") or ""
    det = st.get("shortDetail") or st.get("detail") or st.get("description") or ""
    per, clk = (comp_status or {}).get("period") or 0, (comp_status or {}).get("displayClock") or ""
    if state == "pre": return det
    if state == "post":
        return det.replace("Final", "Final").replace("F/OT", "Final/TE").replace("/OT", "/TE").replace("/SO", "/Penales") if det else "Final"
    if "HALFTIME" in name: return "Descanso"
    if "DELAY" in name or "SUSPEND" in name or "RAIN" in name: return "Retraso" + (f" · {det}" if det and det.lower() not in ("delayed",) else "")
    if "END_PERIOD" in name or "END_OF" in name:
        return f"Fin {_lab(family, league, per)}" if family in ("basketball", "football", "hockey") else det
    if family == "baseball":
        m = re.match(r"(Top|Bot|Mid|End|Bottom)\s+(?:of\s+the\s+)?(\d+)", det, re.I)
        if m:
            w = {"top": "Alta", "bot": "Baja", "bottom": "Baja", "mid": "Mitad", "end": "Fin"}[m.group(1).lower()]
            return f"{w} {m.group(2)}ª"
        return det
    if family == "soccer": return clk or det
    if family == "tennis":
        m = re.match(r"(\d)(?:st|nd|rd|th)$", det.strip())
        return f"Set {m.group(1)}" if m else (det or "En juego")
    return f"{_lab(family, league, per)} {clk}".strip() if per else (det or "En vivo")

def _bases(sit):
    b = [n for n, k in (("1ª", "onFirst"), ("2ª", "onSecond"), ("3ª", "onThird")) if sit.get(k)]
    return ("corredores en " + " y ".join(b)) if b else "bases vacías"

def _yard(txt):
    """'SEA 30' -> ('SEA', 30); '50' -> (None, 50). Posición real del balón según ESPN (possessionText)."""
    m = re.match(r"^\s*([A-Za-z]{2,4})\s+(\d{1,2})\s*$", txt or "")
    if m: return m.group(1).upper(), int(m.group(2))
    m = re.match(r"^\s*(\d{1,2})\s*$", txt or "")
    return (None, int(m.group(1))) if m else (None, None)

def _last(sit):
    lp = sit.get("lastPlay") or {}
    t = lp.get("text") or lp.get("shortText")
    return t if isinstance(t, str) and t.strip() else None

def situation(family, sit, teams_by_id=None):
    """Situación de juego (NFL: posesión/down/yarda; MLB: outs/cuenta/corredores). -> dict(text, ...) o None. Sólo datos que ESPN publica."""
    if not sit: return None
    teams_by_id = teams_by_id or {}
    out = {}
    if family == "football":
        down = sit.get("shortDownDistanceText") or sit.get("downDistanceText")
        if down:
            m = re.match(r"(\d)(?:st|nd|rd|th)\s*&\s*(\w+)", down)
            down = f"{m.group(1)}º y {m.group(2)}" if m else down
        poss = teams_by_id.get(str(sit.get("possession") or "")) or ""
        parts = [p for p in [f"Posesión {poss}" if poss else None, down, sit.get("possessionText")] if p]
        if sit.get("isRedZone"): parts.append("zona roja")
        yt, yn = _yard(sit.get("possessionText"))
        if parts: out = dict(text=" · ".join(parts), possession=str(sit.get("possession") or ""), red_zone=bool(sit.get("isRedZone")),
                             down=sit.get("down") if isinstance(sit.get("down"), int) and sit.get("down") > 0 else None,
                             distance=sit.get("distance") if isinstance(sit.get("distance"), int) else None, yard_team=yt, yard=yn, last_play=_last(sit))
    elif family == "baseball":
        outs = sit.get("outs")
        parts = []
        if outs is not None: parts.append(f"{outs} out{'s' if outs != 1 else ''}")
        if sit.get("balls") is not None and sit.get("strikes") is not None: parts.append(f"cuenta {sit['balls']}-{sit['strikes']}")
        parts.append(_bases(sit))
        bt = ((sit.get("batter") or {}).get("athlete") or {}).get("displayName")
        pt = ((sit.get("pitcher") or {}).get("athlete") or {}).get("displayName")
        if bt: parts.append(f"al bat {bt}")
        if pt: parts.append(f"lanza {pt}")
        out = dict(text=" · ".join(parts), outs=outs, balls=sit.get("balls"), strikes=sit.get("strikes"),
                   bases=[bool(sit.get("onFirst")), bool(sit.get("onSecond")), bool(sit.get("onThird"))], batter=bt, pitcher=pt, last_play=_last(sit))
    return out or None

def live_core(comp, family, league, teams_by_id=None):
    """Bloque 'live' compacto para la lista (sólo juegos en vivo)."""
    st = comp.get("status") or {}
    d = dict(text=status_es(family, league, st), clock=st.get("displayClock"), period=st.get("period"),
             situation=situation(family, comp.get("situation"), teams_by_id))
    ls = {}
    for c in comp.get("competitors", []):
        ls[c.get("homeAway")] = [str((x or {}).get("displayValue", "")) for x in (c.get("linescores") or [])]
    d["linescores"] = ls
    return d

# ------------------------------------------------------------------ detalle en vivo (ESPN summary)
STAT_PICK = {
    "basketball": [("fieldGoalPct", "TC %"), ("threePointFieldGoalPct", "Triples %"), ("freeThrowPct", "Tiros libres %"), ("totalRebounds", "Rebotes"), ("assists", "Asistencias"),
                   ("turnovers", "Pérdidas"), ("steals", "Robos"), ("blocks", "Tapones"), ("fastBreakPoints", "Contraataque"), ("pointsInPaint", "Pts en la pintura")],
    "hockey": [("shotsTotal", "Tiros"), ("hits", "Golpes"), ("blockedShots", "Bloqueos"), ("powerPlayGoals", "Goles en PP"), ("faceoffPercent", "Faceoffs %"), ("takeaways", "Robos"), ("giveaways", "Pérdidas")],
    "football": [("firstDowns", "Primeros downs"), ("totalYards", "Yardas totales"), ("netPassingYards", "Yardas por aire"), ("rushingYards", "Yardas por tierra"),
                 ("thirdDownEff", "3ª oportunidad"), ("turnovers", "Pérdidas de balón"), ("possessionTime", "Tiempo de posesión")],
    "soccer": [("possessionPct", "Posesión %"), ("totalShots", "Tiros"), ("shotsOnTarget", "Tiros a puerta"), ("wonCorners", "Tiros de esquina"), ("foulsCommitted", "Faltas"),
               ("yellowCards", "Amarillas"), ("redCards", "Rojas"), ("offsides", "Fuera de juego")],
    "baseball": [],
}

def team_stats(summ, family):
    teams = (summ.get("boxscore") or {}).get("teams") or []
    by = {t.get("homeAway"): {s.get("name"): s for s in t.get("statistics", []) if s.get("displayValue") not in (None, "")} for t in teams}
    h, a = by.get("home", {}), by.get("away", {})
    rows = []
    for key, lab in STAT_PICK.get(family, []):
        if key in h or key in a:
            rows.append(dict(label=lab, home=(h.get(key) or {}).get("displayValue"), away=(a.get(key) or {}).get("displayValue")))
    if not rows:   # ligas/deportes sin lista: se muestran los primeros con etiqueta de ESPN (en inglés)
        for k, s in list(h.items())[:8]:
            if s.get("label"): rows.append(dict(label=s["label"], home=s.get("displayValue"), away=(a.get(k) or {}).get("displayValue")))
    return rows

def box_top(summ, family, n=3):
    """Mejores anotadores (baloncesto) por equipo, del boxscore real."""
    if family != "basketball": return None
    out = {}
    for t in (summ.get("boxscore") or {}).get("players") or []:
        tid = str((t.get("team") or {}).get("id"))
        st = (t.get("statistics") or [{}])[0]; labels = st.get("labels") or []
        if "PTS" not in labels: continue
        ix = {l: labels.index(l) for l in labels}
        rows = []
        for a in st.get("athletes") or []:
            s = a.get("stats") or []
            if a.get("didNotPlay") or len(s) != len(labels): continue
            pts = _ival(s[ix["PTS"]])
            if pts is None: continue
            rows.append(dict(name=(a.get("athlete") or {}).get("displayName"), min=s[ix["MIN"]] if "MIN" in ix else None, pts=pts,
                             reb=s[ix["REB"]] if "REB" in ix else None, ast=s[ix["AST"]] if "AST" in ix else None, pm=s[ix["+/-"]] if "+/-" in ix else None))
        rows.sort(key=lambda r: -r["pts"])
        out[tid] = rows[:n]
    return out or None

def recent_plays(summ, family, n=6):
    """Últimas jugadas (más reciente primero). Fútbol: eventos clave (goles/tarjetas)."""
    out = []
    if family == "soccer":
        for e in reversed(summ.get("keyEvents") or []):
            ty = ((e.get("type") or {}).get("type") or "")
            if not any(k in ty for k in ("goal", "card", "penalty")): continue
            out.append(dict(text=e.get("text") or (e.get("type") or {}).get("text"), clock=(e.get("clock") or {}).get("displayValue"), scoring=bool(e.get("scoringPlay")), kind=ty))
            if len(out) >= n + 4: break
        return out
    plays = summ.get("plays")
    if not plays and family == "football":
        cur = ((summ.get("drives") or {}).get("current") or {})
        plays = cur.get("plays") or []
        if not plays:
            prev = (summ.get("drives") or {}).get("previous") or []
            plays = prev[-1].get("plays", []) if prev else []
    for p in reversed(plays or []):
        txt = p.get("text") or p.get("shortDescription")
        if not txt: continue
        out.append(dict(text=txt, clock=(p.get("clock") or {}).get("displayValue"), period=(p.get("period") or {}).get("displayValue") or (p.get("period") or {}).get("number"),
                        scoring=bool(p.get("scoringPlay")), score=(f"{p.get('awayScore')}-{p.get('homeScore')}" if p.get("awayScore") is not None else None)))
        if len(out) >= n: break
    return out

def live_detail(summ, family, league, game):
    if not summ or game.get("state") == "pre": return None
    comp = summ["header"]["competitions"][0]
    st = comp.get("status") or {}
    tid = {str(c["team"]["id"]): (c["team"].get("abbreviation") or c["team"].get("displayName")) for c in comp["competitors"]}
    ls = {c.get("homeAway"): [str((x or {}).get("displayValue", "")) for x in (c.get("linescores") or [])] for c in comp["competitors"]}
    return dict(state=game.get("state"), text=status_es(family, league, st), linescores=ls,
                situation=situation(family, summ.get("situation") or ((summ.get("drives") or {}).get("current") or {}).get("situation"), tid),
                stats=team_stats(summ, family), top=box_top(summ, family), plays=recent_plays(summ, family))

# ------------------------------------------------------------------ calificación provisional
def provisional(rows, game, family):
    """rows: [dict(market, selection, line)] -> {'market.selection': dict(state, locked, text)} sólo si el juego está en vivo. NO es resultado final."""
    if game.get("state") != "in" or game.get("sport") == "tenis": return {}
    h, a = _ival(game["home"].get("score")), _ival(game["away"].get("score"))
    if h is None or a is None: return {}
    out = {}
    for r in rows:
        mk, sel, line = r.get("market"), r.get("selection"), r.get("line")
        if mk not in ("ml", "spread", "total", "dc"): continue
        try: st = settle(mk, sel, line, dict(home=h, away=a), three_way=(family == "soccer"))
        except Exception: st = None
        if st is None: continue
        s = {"GANADO": "ganando", "MEDIO_GANADO": "ganando", "PERDIDO": "perdiendo", "MEDIO_PERDIDO": "perdiendo", "PUSH": "empatando"}.get(st)
        if not s: continue
        locked = False
        if mk == "total" and line is not None:
            tot = h + a
            if sel == "over" and tot > line: locked = True            # el total sólo sube: ya no puede perder
            elif sel == "under" and tot >= line and s == "perdiendo": locked = True   # ya se pasó: ya no puede ganar
        out[f"{mk}.{sel}"] = dict(state=s, locked=locked, score=f"{game['away'].get('score')}-{game['home'].get('score')}")
    return out
