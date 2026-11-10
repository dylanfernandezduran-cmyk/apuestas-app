"""Filtro de calidad de picks NRNM y panel de 6 señales.

Predicción (ganador) y pick principal salen del mismo pFinal.
El pick publicado coincide siempre con el lado predicho; si no hay consenso
de señales, el juego queda PASS/REVISAR sin pick principal.
Nunca se inventan cifras: lo que falta se marca «sin dato».
"""
from __future__ import annotations

from . import core as CORE
from . import model as M

SIGNALS = (
    ("modelo", "Modelo (pFinal)"),
    ("movimiento", "Movimiento de línea"),
    ("rlm", "RLM / dinero inteligente"),
    ("tendencias", "Tendencias"),
    ("lesiones", "Lesiones y alineaciones"),
    ("fisico", "Contexto físico / clima"),
)

MIN_PRESENT = 4
MIN_AGREE = 4
DAILY_CAP = 10
CONF_OK = ("Media", "Alta")


def _n_games(mdl):
    if not mdl:
        return 0
    if mdl.get("sample") is not None:
        try:
            return int(mdl["sample"])
        except (TypeError, ValueError):
            pass
    try:
        return int(mdl.get("n_home") or 0) + int(mdl.get("n_away") or 0)
    except (TypeError, ValueError):
        return 0


def pfinal_view(cands=None, mdl=None, odds=None, fam=None):
    """Ganador y probs a partir del mismo pFinal que usan los candidatos."""
    ml = {c["side"]: c for c in (cands or []) if c.get("market") == "ML" and c.get("p_final") is not None and c.get("side")}
    if ml:
        probs = {s: float(ml[s]["p_final"]) for s in ml}
        side = max(probs, key=probs.get)
        return dict(winner=dict(side=side, p=probs[side], probs=probs, src="pfinal"))
    if not mdl:
        return None
    n = _n_games(mdl)
    nv = ((odds or {}).get("nv") or {}).get("ml") or {}

    def blend(pm, pnv):
        if pm is None:
            return pnv
        if pnv is None:
            return pm
        try:
            return CORE.p_final(pm, pnv, n)
        except Exception:
            return pm

    if fam == "soccer" or mdl.get("p_draw") is not None:
        raw = (("home", mdl.get("p_home"), nv.get("home")),
               ("draw", mdl.get("p_draw"), nv.get("draw")),
               ("away", mdl.get("p_away"), nv.get("away")))
        probs = {k: blend(pm, pnv) for k, pm, pnv in raw if blend(pm, pnv) is not None}
        z = sum(probs.values()) or 1.0
        probs = {k: v / z for k, v in probs.items()}
    else:
        ph = blend(mdl.get("p_home"), nv.get("home"))
        if ph is None:
            return None
        probs = dict(home=float(ph), away=1.0 - float(ph))
    side = max(probs, key=probs.get)
    return dict(winner=dict(side=side, p=probs[side], probs=probs, src="pfinal"))


def _score_pair(pred, fam=None):
    sc = (pred or {}).get("score") or {}
    if fam == "tennis" or (pred or {}).get("kind") == "tenis":
        g = sc.get("games")
        if isinstance(g, (list, tuple)) and len(g) == 2:
            return g[0], g[1]
        if sc.get("home") is not None and sc.get("away") is not None:
            return sc["home"], sc["away"]
        return None, None
    if sc.get("home") is None or sc.get("away") is None:
        return None, None
    return sc["home"], sc["away"]


def consistent_with_pred(pred, cand, fam=None):
    """True si el candidato encaja con el ganador / marcador / total / hándicap predichos."""
    if not pred or not cand:
        return False
    mk, side, line = cand.get("market"), cand.get("side"), cand.get("line")
    if not mk or not side:
        return False
    h, a = _score_pair(pred, fam)
    if mk == "ML":
        w = ((pred.get("winner") or {}).get("side"))
        return w is not None and side == w
    if mk in ("Total", "OU") and h is not None:
        t = pred.get("total") or {}
        if t.get("side") and (line is None or t.get("line") is None or float(t["line"]) == float(line)):
            return side == t["side"]
        if line is None:
            return False
        tot = h + a
        try:
            L = float(line)
        except (TypeError, ValueError):
            return False
        if tot == L:
            return False
        return (tot > L) == (side == "over")
    if mk == "Spread" and h is not None:
        s = pred.get("spread") or {}
        if s.get("side") and (line is None or s.get("line") is None):
            return side == s["side"]
        L = line if line is not None else s.get("line")
        if L is None:
            return side == ((pred.get("winner") or {}).get("side"))
        try:
            Lh = float(L) if (s.get("side") is None or side == "home" or cand.get("side") == "home") else -float(L)
        except (TypeError, ValueError):
            return False
        # línea del LOCAL: si el candidato es visita, la línea viene del lado visita
        if side == "away" and line is not None and s.get("line") is not None and abs(float(line) - float(s["line"])) > 1e-9:
            # candidato trae línea del away: convertir a línea del local
            Lh = -float(line)
        elif side == "away" and line is not None and s.get("line") is None:
            Lh = -float(line)
        elif side == "home" and line is not None:
            Lh = float(line)
        elif s.get("line") is not None:
            Lh = float(s["line"])
        d = h - a + Lh
        if d == 0:
            return False
        return (d > 0) == (side == "home")
    if mk == "BTTS" and h is not None:
        b = pred.get("btts") or {}
        if b.get("side"):
            return side == b["side"]
        both = h > 0 and a > 0
        return (side == "yes") == both
    if mk in ("Corners", "corners"):
        c = pred.get("corners") or {}
        return (not c) or side == c.get("side")
    return False


def _main_side_ok(pred, cand):
    """El pick principal (ML o spread) debe coincidir con el lado ganador / hándicap predicho."""
    if not pred or not cand:
        return False
    mk = cand.get("market")
    if mk == "ML":
        return cand.get("side") == ((pred.get("winner") or {}).get("side"))
    if mk == "Spread":
        sp = (pred.get("spread") or {}).get("side")
        if sp:
            return cand.get("side") == sp
        return cand.get("side") == ((pred.get("winner") or {}).get("side"))
    return False


def _sig(key, verdict, detail, figures=None):
    label = dict(SIGNALS).get(key, key)
    return dict(key=key, label=label, verdict=verdict, detail=detail or "sin dato", figures=figures or {})


def _pct(x, digits=1):
    if x is None:
        return "sin dato"
    try:
        return f"{float(x) * 100:.{digits}f}%" if abs(float(x)) <= 1.5 else f"{float(x):.{digits}f}%"
    except (TypeError, ValueError):
        return "sin dato"


def _am(o):
    if o is None:
        return "sin dato"
    try:
        o = int(o)
    except (TypeError, ValueError):
        return "sin dato"
    return f"+{o}" if o > 0 else str(o)


def _modelo(cand, pred):
    pf = cand.get("p_final")
    pnv = cand.get("p_nv")
    pm = cand.get("p_model")
    ev = cand.get("ev")
    figs = dict(p_final=pf, p_nv=pnv, p_model=pm, ev=ev, edge=cand.get("edge"))
    w = ((pred or {}).get("winner") or {})
    bits = [f"pFinal { _pct(pf) }", f"modelo {_pct(pm)}", f"mercado s/vig {_pct(pnv)}"]
    if ev is not None:
        bits.append(f"EV {ev * 100:+.1f}%")
    if w.get("side") is not None and w.get("src") == "pfinal":
        bits.append(f"ganador pFinal: {w['side']} ({_pct(w.get('p'))})")
    if pf is None:
        return _sig("modelo", "sin_dato", "pFinal: sin dato", figs)
    # a favor si este lado es el de mayor pFinal (o, en totales, pFinal > 0.5)
    if cand.get("market") == "ML" and w.get("side"):
        ok = cand.get("side") == w["side"]
    else:
        ok = float(pf) >= 0.5
    return _sig("modelo", "a_favor" if ok else "en_contra", " · ".join(bits), figs)


def _moves_for(out, cand):
    """Apertura vs actual y etiquetas STEAM/REZAGADA, sin inventar."""
    figs = dict(open_odds=None, now_odds=None, open_line=None, now_line=None, d_nv_pp=None, tags=[], books=[])
    mk = {"ML": "ml", "Spread": "spread", "Total": "total"}.get(cand.get("market") or "")
    side = cand.get("side")
    mv = ((out.get("market") or {}).get("movement") or {})
    toward = None
    detail_parts = []
    if mk == "ml" and isinstance(mv.get("ml"), dict):
        row = mv["ml"].get(side) or {}
        figs["open_odds"] = row.get("open")
        figs["now_odds"] = row.get("cur")
        figs["d_nv_pp"] = row.get("d_nv_pp")
        if row:
            detail_parts.append(f"apertura {_am(row.get('open'))} → actual {_am(row.get('cur'))}"
                                + (f" ({row['d_nv_pp']:+.1f} pp s/vig)" if row.get("d_nv_pp") is not None else ""))
            if row.get("d_nv_pp") is not None:
                toward = row["d_nv_pp"] >= 0.5
                if abs(row["d_nv_pp"]) < 0.5:
                    toward = None  # movimiento irrelevante
    elif mk == "spread" and mv.get("spread"):
        row = mv["spread"]
        figs["open_line"] = row.get("open_line")
        figs["now_line"] = row.get("cur_line")
        d = row.get("d_line_home")
        figs["d_line"] = d
        detail_parts.append(f"línea local {row.get('open_line')} → {row.get('cur_line')}"
                            + (f" ({d:+.2f} pts)" if d is not None else ""))
        if d is not None:
            # línea del local baja (más negativa) favorece al local
            if side == "home":
                toward = d < -0.25
                if abs(d) < 0.25:
                    toward = None
            elif side == "away":
                toward = d > 0.25
                if abs(d) < 0.25:
                    toward = None
    elif mk == "total" and mv.get("total"):
        row = mv["total"]
        figs["open_line"] = row.get("open_line")
        figs["now_line"] = row.get("cur_line")
        d = row.get("d_line")
        figs["d_line"] = d
        detail_parts.append(f"total {row.get('open_line')} → {row.get('cur_line')}"
                            + (f" ({d:+.2f} pts)" if d is not None else ""))
        if d is not None:
            if side == "over":
                toward = d > 0.25
            elif side == "under":
                toward = d < -0.25
            if abs(d) < 0.25:
                toward = None

    # historial por casa + detector
    alerts = []
    try:
        from . import history as HIST, lineas as LN
        g = out.get("game") or {}
        if g.get("league") and g.get("id"):
            ser = ((out.get("market") or {}).get("history")) or HIST.series(g["league"], g["id"])
            figs["n_points"] = ser.get("n_points") if isinstance(ser, dict) else None
            if isinstance(ser, dict) and ser.get("n_points"):
                # por casa: apertura → actual
                books = []
                lines = (ser.get("lines") or {}).get(mk or "", {})
                for book, sides in lines.items():
                    pts = (sides or {}).get(side) or []
                    if len(pts) >= 1:
                        books.append(dict(book=book, open_odds=pts[0][2] if pts[0] else None,
                                          now_odds=pts[-1][2] if pts[-1] else None,
                                          open_line=pts[0][1] if pts[0] else None,
                                          now_line=pts[-1][1] if pts[-1] else None, n=len(pts)))
                figs["books"] = books
                if books:
                    bits = []
                    for b in books[:8]:
                        bits.append(f"{b['book']} {_am(b.get('open_odds'))}→{_am(b.get('now_odds'))}")
                    detail_parts.append("por casa: " + "; ".join(bits))
                try:
                    alerts = [a for a in LN.detect(ser) if a.get("market") == (mk or "") and a.get("side") == side]
                except Exception:
                    alerts = []
    except Exception:
        alerts = []

    tags = []
    for a in alerts:
        tags.extend(a.get("tags") or [])
        if figs.get("open_odds") is None:
            figs["open_odds"] = a.get("open_odds")
            figs["now_odds"] = a.get("now_odds")
        if a.get("pp") is not None and figs.get("d_nv_pp") is None:
            figs["d_nv_pp"] = a["pp"]
            if toward is None:
                toward = a["pp"] > 0
        detail_parts.append(f"consenso {a.get('pp'):+.1f} pp" if a.get("pp") is not None else "movimiento detectado")
    figs["tags"] = tags
    if tags:
        detail_parts.append("etiquetas: " + ", ".join(tags))

    if toward is True:
        return _sig("movimiento", "a_favor", " · ".join(detail_parts) or "la línea se movió a favor", figs)
    if toward is False:
        return _sig("movimiento", "en_contra", " · ".join(detail_parts) or "la línea se movió en contra", figs)
    if detail_parts:
        return _sig("movimiento", "neutral", " · ".join(detail_parts) + " · sin movimiento relevante", figs)
    return _sig("movimiento", "sin_dato", "Movimiento de línea: sin dato (aún no hay historial de apertura vs actual)", figs)


def _rlm(cand, out):
    sig = (cand or {}).get("signals") or {}
    tickets, money = sig.get("tickets"), sig.get("money")
    figs = dict(tickets=tickets, money=money, rlm=sig.get("rlm"), rlm_side=sig.get("rlm_side"),
                sharp=sig.get("sharp"), verdict=sig.get("verdict"), tags=sig.get("tags"))
    # respaldo desde splits del mercado si el candidato no trae signals
    if tickets is None or money is None:
        sp = ((out.get("market") or {}).get("splits") or {})
        mk = {"ML": "ml", "Spread": "spread", "Total": "total"}.get((cand or {}).get("market") or "")
        row = (sp.get(mk) or {}).get((cand or {}).get("side")) if mk else None
        if isinstance(row, dict):
            tickets = row.get("tickets") if tickets is None else tickets
            money = row.get("money") if money is None else money
            figs["tickets"], figs["money"] = tickets, money
        elif isinstance(row, (list, tuple)) and row:
            last = row[-1]
            if len(last) >= 3:
                tickets = last[1] if tickets is None else tickets
                money = last[2] if money is None else money
                figs["tickets"], figs["money"] = tickets, money
    parts = []
    if tickets is not None or money is not None:
        parts.append(f"% apuestas {tickets if tickets is not None else 'sin dato'} / % dinero {money if money is not None else 'sin dato'}")
    if sig.get("rlm"):
        parts.append(f"RLM hacia {sig.get('rlm_side') or 'un lado'}")
    tags = sig.get("tags") or []
    if tags:
        labs = [t[1] if isinstance(t, (list, tuple)) and len(t) > 1 else str(t) for t in tags]
        parts.append(", ".join(labs))
    verd = sig.get("verdict")
    if verd in ("a_favor", "en_contra", "mixto", "neutral"):
        return _sig("rlm", verd, " · ".join(parts) or verd, figs)
    if tickets is None and money is None and not sig.get("rlm") and not tags:
        return _sig("rlm", "sin_dato", "% apuestas / % dinero / RLM: sin dato", figs)
    # heurística mínima si hay splits crudos sin verdict
    if tickets is not None and money is not None:
        try:
            t, m = float(tickets), float(money)
            if t <= 100:
                pass
            gap = m - t
            if gap >= 10 and m >= 50:
                return _sig("rlm", "a_favor", " · ".join(parts) + " · más dinero que tickets en este lado", figs)
            if gap <= -10 and t >= 55:
                return _sig("rlm", "a_favor", " · ".join(parts) + " · posible RLM (más tickets que dinero)", figs)
            return _sig("rlm", "neutral", " · ".join(parts), figs)
        except (TypeError, ValueError):
            pass
    return _sig("rlm", "sin_dato", " · ".join(parts) or "% apuestas / % dinero / RLM: sin dato", figs)


def _form_of(teams, tid):
    if not teams or tid is None:
        return None
    return teams.get(tid) or teams.get(str(tid))


def _trends(out, cand, pred):
    g = out.get("game") or {}
    teams = out.get("teams") or {}
    ats = out.get("ats") or []
    mk = cand.get("market")
    side = cand.get("side")
    figs = {}
    parts = []
    # forma reciente del lado elegidos
    if mk in ("ML", "Spread") and side in ("home", "away"):
        tid = (g.get(side) or {}).get("id")
        oid = (g.get("away" if side == "home" else "home") or {}).get("id")
        me, opp = _form_of(teams, tid), _form_of(teams, oid)
        def wr(s, key="last5"):
            r = (s or {}).get(key) or {}
            n = r.get("n") or 0
            if not n:
                return None
            return dict(w=r.get("w"), l=r.get("l"), d=r.get("d"), n=n, text=r.get("text"), rate=(r.get("w") or 0) / n)
        m5, o5 = wr(me), wr(opp)
        m10, o10 = wr(me, "last10"), wr(opp, "last10")
        figs["last5"], figs["last10"] = m5, m10
        figs["opp_last5"] = o5
        if me and me.get("streak"):
            parts.append(f"racha {me['streak']}")
            figs["streak"] = me["streak"]
        if m5:
            parts.append(f"últimos 5: {m5.get('text')} ({_pct(m5['rate'])})")
        if m10:
            parts.append(f"últimos 10: {m10.get('text')}")
        if o5:
            parts.append(f"rival últimos 5: {o5.get('text')}")
        # ATS si ESPN lo publicó
        ats_txt = []
        for row in ats:
            recs = row.get("records") or []
            name = row.get("team") or ""
            for rec in recs:
                typ = (rec.get("type") or rec.get("displayValue") or "").lower()
                sm = rec.get("summary") or rec.get("displayValue")
                if sm and ("ats" in typ or typ == "spread" or "against" in typ):
                    ats_txt.append(f"{name} ATS {sm}")
                if sm and typ in ("ou", "over-under", "overunder") or (sm and "ou" == typ):
                    ats_txt.append(f"{name} O/U {sm}")
        if ats_txt:
            parts.append("; ".join(ats_txt[:4]))
            figs["ats"] = ats_txt
        if m5 and o5 and m5["n"] >= 3 and o5["n"] >= 3:
            if m5["rate"] > o5["rate"] + 0.05:
                return _sig("tendencias", "a_favor", " · ".join(parts), figs)
            if m5["rate"] + 0.05 < o5["rate"]:
                return _sig("tendencias", "en_contra", " · ".join(parts), figs)
            return _sig("tendencias", "neutral", " · ".join(parts) + " · forma pareja", figs)
        if m5 and m5["n"] >= 3:
            if m5["rate"] >= 0.6:
                return _sig("tendencias", "a_favor", " · ".join(parts), figs)
            if m5["rate"] <= 0.35:
                return _sig("tendencias", "en_contra", " · ".join(parts), figs)
            return _sig("tendencias", "neutral", " · ".join(parts), figs)
        if parts:
            return _sig("tendencias", "sin_dato", " · ".join(parts) + " · muestra insuficiente", figs)
        return _sig("tendencias", "sin_dato", "Tendencias ATS/forma: sin dato", figs)
    if mk == "Total":
        # promedio combinado reciente vs línea
        line = cand.get("line") or ((pred or {}).get("total") or {}).get("line")
        avgs = []
        for s in ("home", "away"):
            tid = (g.get(s) or {}).get("id")
            rec = (_form_of(teams, tid) or {}).get("recent") or []
            r5 = rec[:5]
            if r5:
                avg = sum((r.get("pf") or 0) + (r.get("pa") or 0) for r in r5) / len(r5)
                avgs.append(avg)
                parts.append(f"{(g.get(s) or {}).get('short') or s}: {avg:.1f} pts/juegos combinados (últimos {len(r5)})")
        figs["recent_combined"] = avgs
        figs["line"] = line
        if avgs and line is not None:
            mean = sum(avgs) / len(avgs)
            parts.append(f"línea {line:g}")
            if side == "over":
                verd = "a_favor" if mean > float(line) + 0.5 else ("en_contra" if mean < float(line) - 0.5 else "neutral")
            else:
                verd = "a_favor" if mean < float(line) - 0.5 else ("en_contra" if mean > float(line) + 0.5 else "neutral")
            return _sig("tendencias", verd, " · ".join(parts), figs)
        if parts:
            return _sig("tendencias", "sin_dato", " · ".join(parts) + " · línea del total: sin dato", figs)
        return _sig("tendencias", "sin_dato", "Tendencias O/U: sin dato", figs)
    return _sig("tendencias", "sin_dato", "Tendencias: sin dato", figs)


def _inj_out(entries):
    out = []
    for e in entries or []:
        st = (e.get("status") or e.get("status_es") or "")
        bucket = (e.get("bucket") or "").lower()
        name = e.get("name") or e.get("nombre")
        if not name:
            continue
        low = st.lower()
        if bucket in ("out", "ir", "susp") or any(k in low for k in ("out", "injured reserve", "suspension", "inactive", "il")):
            if "day-to-day" in low or "probable" in low or "questionable" in low or "doubtful" in low:
                if "out" not in low and "reserve" not in low:
                    continue
            out.append(f"{name} ({st})")
    return out


def _lesiones(out, cand):
    g = out.get("game") or {}
    side = cand.get("side") if cand.get("market") in ("ML", "Spread") else None
    figs = {}
    parts = []
    # alineaciones
    lu = out.get("lineups") or {}
    sides_lu = (lu.get("sides") if isinstance(lu, dict) else None) or {}
    confirmed = []
    unpublished = []
    for s in ("home", "away"):
        block = sides_lu.get(s) or {}
        st = block.get("status")
        if st == "confirmado":
            confirmed.append(s)
            n = len(block.get("players") or block.get("pls") or [])
            parts.append(f"alineación {s} confirmada" + (f" ({n} jug.)" if n else ""))
        elif st == "proyectado":
            parts.append(f"alineación {s} proyectada (no confirmada)")
        elif st == "sin_publicar":
            unpublished.append(s)
    figs["lineups"] = {s: (sides_lu.get(s) or {}).get("status") for s in ("home", "away")} if sides_lu else {}

    # QB / estrella fuera
    qb = ((out.get("model") or {}).get("qb_out") or {})
    qb_sides = qb.get("sides") or []
    figs["qb_out"] = qb_sides
    key_names = (out.get("model") or {}).get("key_injuries") or []
    figs["key_injuries"] = key_names

    full = ((out.get("injuries_full") or {}).get("sides") or {})
    inj_by_side = {}
    for s in ("home", "away"):
        entries = (full.get(s) or {}).get("entries")
        if not entries:
            tid = (g.get(s) or {}).get("id")
            entries = (out.get("injuries") or {}).get(tid) or (out.get("injuries") or {}).get(str(tid) or "")
        outs = _inj_out(entries)
        inj_by_side[s] = outs
        if outs:
            parts.append(f"{s}: fuera {', '.join(outs[:4])}")
    figs["out"] = inj_by_side

    if not sides_lu and not qb_sides and not key_names and not any(inj_by_side.values()) and not (out.get("injuries") or {}):
        return _sig("lesiones", "sin_dato", "Lesiones y alineaciones: sin dato", figs)

    # veredicto relativo al lado del pick (ML/spread); en totales, una baja ofensiva clave va en contra del over
    pick_team = side if side in ("home", "away") else None
    opp = "away" if pick_team == "home" else ("home" if pick_team == "away" else None)
    qb_pick_out = any(x.get("out") and x.get("side") == pick_team for x in qb_sides)
    qb_opp_out = any(x.get("out") and x.get("side") == opp for x in qb_sides)
    if qb.get("notes"):
        parts.extend(qb["notes"])

    if cand.get("market") == "Total":
        # star/QB out usually lowers scoring
        if qb.get("applied") or key_names:
            verd = "en_contra" if cand.get("side") == "over" else "a_favor"
            return _sig("lesiones", verd, " · ".join(parts) or "baja clave afecta el total", figs)
        if confirmed and not key_names:
            return _sig("lesiones", "neutral", " · ".join(parts) or "alineaciones sin baja clave reportada", figs)
        if parts:
            return _sig("lesiones", "neutral", " · ".join(parts), figs)
        return _sig("lesiones", "sin_dato", "Lesiones y alineaciones: sin dato", figs)

    if qb_pick_out:
        return _sig("lesiones", "en_contra", " · ".join(parts) or "QB/estrella del lado elegido está fuera", figs)
    if qb_opp_out:
        return _sig("lesiones", "a_favor", " · ".join(parts) or "QB/estrella del rival está fuera", figs)

    # lesionados clave del summary (líderes)
    if key_names and pick_team:
        # no siempre sabemos el lado del lesionado en key_names; si hay injuries indexados, cruce
        pick_outs = inj_by_side.get(pick_team) or []
        opp_outs = inj_by_side.get(opp) or []
        if pick_outs and not opp_outs:
            return _sig("lesiones", "en_contra", " · ".join(parts), figs)
        if opp_outs and not pick_outs:
            return _sig("lesiones", "a_favor", " · ".join(parts), figs)
        return _sig("lesiones", "neutral", " · ".join(parts) + " · bajas en ambos o lado no atribuible", figs)

    if pick_team and (inj_by_side.get(pick_team) or inj_by_side.get(opp)):
        n_p, n_o = len(inj_by_side.get(pick_team) or []), len(inj_by_side.get(opp) or [])
        if n_p > n_o + 1:
            return _sig("lesiones", "en_contra", " · ".join(parts), figs)
        if n_o > n_p + 1:
            return _sig("lesiones", "a_favor", " · ".join(parts), figs)
        return _sig("lesiones", "neutral", " · ".join(parts) or "bajas similares", figs)

    if confirmed:
        return _sig("lesiones", "a_favor", " · ".join(parts) or "alineaciones confirmadas, sin baja clave", figs)
    if parts:
        return _sig("lesiones", "sin_dato" if unpublished and not confirmed else "neutral",
                    " · ".join(parts), figs)
    return _sig("lesiones", "sin_dato", "Lesiones y alineaciones: sin dato", figs)


def _compute_rest(out):
    if out.get("rest"):
        return out["rest"]
    try:
        from .data import parse_dt, CDMX
    except Exception:
        return {}
    g = out.get("game") or {}
    gd = parse_dt(g.get("date"))
    if not gd:
        return {}
    sport = g.get("sport") or ""
    fam = "basketball" if sport in ("nba", "ncaab", "baloncesto") else (
        "hockey" if sport in ("nhl", "hockey") else sport)
    gday = gd.astimezone(CDMX).date()
    teams = out.get("teams") or {}
    rest = {}
    for s in ("home", "away"):
        tid = (g.get(s) or {}).get("id")
        recent = (_form_of(teams, tid) or {}).get("recent") or []
        dates = []
        for r in recent:
            d = parse_dt(r.get("date"))
            if d:
                day = d.astimezone(CDMX).date()
                if day < gday:
                    dates.append(day)
        if not dates:
            continue
        last = max(dates)
        days = (gday - last).days - 1
        n7 = sum(1 for x in dates if 0 <= (gday - x).days <= 7)
        rest[s] = dict(days=days, b2b=(days == 0 and fam in ("basketball", "hockey")), n7=n7, last=last.isoformat())
    return rest


def _wx_bits(wx):
    if not wx:
        return [], {}
    figs = {}
    parts = []
    status = wx.get("status")
    if status == "sin_dato" and not wx.get("espn") and wx.get("temp_f") is None and wx.get("temp") is None:
        return ["clima: sin dato"], dict(status="sin_dato", reason=wx.get("reason"))
    temp = wx.get("temp_c") if wx.get("temp_c") is not None else wx.get("temp")
    temp_f = wx.get("temp_f") or (wx.get("espn") or {}).get("temp_f")
    wind = wx.get("wind") or wx.get("wind_kmh") or wx.get("gust") or (wx.get("espn") or {}).get("gust")
    precip = wx.get("precip") or wx.get("precipitation") or (wx.get("espn") or {}).get("precip")
    cond = wx.get("condition") or wx.get("summary") or wx.get("text")
    indoor = wx.get("indoor")
    if indoor:
        parts.append("estadio cubierto")
        figs["indoor"] = True
    if temp is not None:
        parts.append(f"{temp:g} °C")
        figs["temp_c"] = temp
    elif temp_f is not None:
        parts.append(f"{temp_f:g} °F")
        figs["temp_f"] = temp_f
    if wind is not None:
        parts.append(f"viento/ráfaga {wind}")
        figs["wind"] = wind
    if precip is not None:
        parts.append(f"precipitación {precip}")
        figs["precip"] = precip
    if cond:
        parts.append(str(cond))
        figs["condition"] = cond
    if wx.get("reason") and not parts:
        parts.append(f"clima: {wx['reason']}")
    return parts, figs


def _fisico(out, cand):
    rest = _compute_rest(out)
    g = out.get("game") or {}
    wx = out.get("weather") or g.get("weather") or {}
    side = cand.get("side") if cand.get("market") in ("ML", "Spread") else None
    parts, figs = [], dict(rest=rest)
    for s in ("home", "away"):
        r = rest.get(s) or {}
        if not r:
            continue
        bit = f"{s}: {r.get('days')} día(s) de descanso"
        if r.get("b2b"):
            bit += " · back-to-back"
        if r.get("n7") is not None:
            bit += f" · {r['n7']} juegos en 7 días"
        parts.append(bit)
    wx_parts, wx_figs = _wx_bits(wx)
    figs["weather"] = wx_figs
    parts.extend(wx_parts)

    if not rest and (not wx or wx.get("status") == "sin_dato") and not wx_figs and not any(wx_parts):
        return _sig("fisico", "sin_dato", "Descanso, viajes y clima: sin dato", figs)

    # veredicto
    if side in ("home", "away") and rest:
        me, opp = rest.get(side) or {}, rest.get("away" if side == "home" else "home") or {}
        if me.get("b2b") and not opp.get("b2b"):
            return _sig("fisico", "en_contra", " · ".join(parts), figs)
        if opp.get("b2b") and not me.get("b2b"):
            return _sig("fisico", "a_favor", " · ".join(parts), figs)
        if me.get("days") is not None and opp.get("days") is not None:
            if me["days"] >= opp["days"] + 2:
                return _sig("fisico", "a_favor", " · ".join(parts), figs)
            if opp["days"] >= me["days"] + 2:
                return _sig("fisico", "en_contra", " · ".join(parts), figs)

    # clima adverso para totales al aire libre
    if cand.get("market") == "Total" and not (wx_figs.get("indoor") or wx.get("indoor")):
        wind = wx_figs.get("wind")
        precip = wx_figs.get("precip")
        adverse = False
        try:
            if wind is not None and float(wind) >= 25:
                adverse = True
        except (TypeError, ValueError):
            pass
        try:
            if precip is not None and float(precip) > 0:
                adverse = True
        except (TypeError, ValueError):
            if precip and str(precip).lower() not in ("0", "0.0", "none"):
                adverse = True
        if adverse:
            verd = "en_contra" if cand.get("side") == "over" else "a_favor"
            return _sig("fisico", verd, " · ".join(parts) or "clima adverso para el total", figs)

    if parts:
        return _sig("fisico", "neutral", " · ".join(parts), figs)
    return _sig("fisico", "sin_dato", "Descanso, viajes y clima: sin dato", figs)


def panel(out, cand, pred=None):
    """Las 6 señales para un candidato, con cifras reales o «sin dato»."""
    pred = pred or out.get("pred")
    sigs = [
        _modelo(cand or {}, pred),
        _moves_for(out, cand or {}),
        _rlm(cand or {}, out),
        _trends(out, cand or {}, pred),
        _lesiones(out, cand or {}),
        _fisico(out, cand or {}),
    ]
    present = [s for s in sigs if s["verdict"] != "sin_dato"]
    agree = [s for s in present if s["verdict"] == "a_favor"]
    against = [s for s in present if s["verdict"] == "en_contra"]
    return dict(signals=sigs, n_present=len(present), n_agree=len(agree), n_against=len(against),
                n_required=MIN_PRESENT, min_agree=MIN_AGREE)


def publish_reason(cand, analysis, conf, status):
    """None si se puede publicar; si no, motivo en español."""
    ev = cand.get("ev") if cand else None
    level = (conf or {}).get("level") if isinstance(conf, dict) else conf
    if not cand:
        return "sin candidato alineado con la predicción (pFinal)"
    if status == "REVISAR" or cand.get("status") == "REVISAR" or cand.get("divergence_high"):
        return "REVISAR (divergencia modelo vs mercado > 10 pp)"
    if ev is None:
        return "EV: sin dato (no se publica sin valor esperado)"
    if ev <= 0:
        return f"EV no positivo ({ev * 100:+.1f}%)"
    if level not in CONF_OK:
        return f"confianza {level or 'sin dato'} (se exige Media o Alta)"
    n_pres = (analysis or {}).get("n_present") or 0
    n_ag = (analysis or {}).get("n_agree") or 0
    if n_pres < MIN_PRESENT:
        return f"solo {n_pres} señales con dato (se exigen {MIN_PRESENT})"
    if n_ag < MIN_AGREE:
        return f"{n_ag}/{n_pres} señales a favor (se exigen {MIN_AGREE})"
    return None


def _fam(out):
    g = out.get("game") or {}
    if out.get("kind") == "tennis" or g.get("sport") == "tenis":
        return "tennis"
    if g.get("sport") == "futbol":
        return "soccer"
    return g.get("sport")


def _rank_key(c):
    ev = c.get("ev") if c.get("ev") is not None else -999
    return (ev, c.get("edge") or 0, c.get("p_final") or 0)


def apply(out):
    """Filtra picks de un análisis: 1 principal máx., alineado a pFinal, o PASS/REVISAR."""
    picks = out.get("picks")
    pred = out.get("pred")
    if not picks:
        return out
    fam = _fam(out)
    cands = list(picks.get("candidates") or [])
    conf = picks.get("confidence") or {}
    raw_status = picks.get("status")
    mains, sugg = [], []
    for c in cands:
        ok_score = consistent_with_pred(pred, c, fam)
        c["consistent"] = ok_score
        if not ok_score:
            continue
        if c.get("market") in ("ML", "Spread") and _main_side_ok(pred, c):
            mains.append(c)
        elif c.get("status") in ("PICK", "LEAN"):
            sugg.append(c)
    mains.sort(key=_rank_key, reverse=True)
    sugg.sort(key=_rank_key, reverse=True)
    # un principal por juego: el de mayor EV entre los alineados
    cand = mains[0] if mains else None
    analysis = panel(out, cand or (cands[0] if cands else {}), pred) if (cand or cands) else dict(
        signals=[_sig(k, "sin_dato", "sin dato") for k, _ in SIGNALS], n_present=0, n_agree=0, n_against=0,
        n_required=MIN_PRESENT, min_agree=MIN_AGREE)
    reason = None
    published = False
    status = raw_status or "PASS"
    lean = cand
    if cand is None:
        # ¿el mejor EV contradice pFinal?
        best = max(cands, key=_rank_key) if cands else None
        if best and not consistent_with_pred(pred, best, fam):
            reason = "el mejor EV contradice la Predicción NRNM (mismo pFinal); el juego se deja en PASS"
            analysis = panel(out, best, pred)
            lean = None  # no hay pick principal
        else:
            reason = "ningún candidato de ML/spread coincide con el ganador predicho (pFinal)"
            lean = None
        status = "REVISAR" if raw_status == "REVISAR" else "PASS"
    else:
        reason = publish_reason(cand, analysis, conf, raw_status or cand.get("status"))
        if reason is None:
            published = True
            status = cand.get("status") if cand.get("status") in ("PICK", "LEAN") else "PICK"
            lean = cand
        else:
            published = False
            status = "REVISAR" if (raw_status == "REVISAR" or cand.get("status") == "REVISAR") else "PASS"
    picks["lean"] = lean
    picks["status"] = status
    picks["published"] = published
    picks["quality_ok"] = published
    picks["discard_reason"] = None if published else reason
    picks["analysis"] = analysis
    picks["suggestions"] = sugg
    # 1 principal: no dejar candidatos PICK del lado contrario como si fueran accionables
    out["picks"] = picks
    out["analysis"] = analysis
    return out


def refresh(out):
    """Reevalúa señales después de enrich.detail (alineaciones, clima, descanso)."""
    if out and out.get("picks"):
        apply(out)
    return out


def _item_rank(it):
    l = it.get("lean") or {}
    ev = l.get("ev") if l.get("ev") is not None else -999
    cw = {"Alta": 2, "Media": 1, "Baja": 0}
    conf = ((it.get("confidence") or {}).get("level")) or l.get("conf_level")
    return (ev, cw.get(conf, 0), l.get("edge") or 0)


def cap_daily(items, limit=DAILY_CAP):
    """Deja como publicados como máximo `limit` picks principales, ranqueados por EV+confianza."""
    items = list(items or [])
    pub = [it for it in items if it.get("published")]
    pub.sort(key=_item_rank, reverse=True)
    keep = {id(it) for it in pub[:limit]}
    for it in pub[limit:]:
        it["published"] = False
        it["capped"] = True
        it["discard_reason"] = f"fuera del tope de {limit} picks principales del día (EV + confianza)"
        if it.get("status") == "PICK":
            it["status"] = "PASS"
        p = it.get("picks")
        if isinstance(p, dict):
            p["published"] = False
            p["discard_reason"] = it["discard_reason"]
    # reordenar: publicados primero
    items.sort(key=lambda r: (0 if r.get("published") else 1, -_item_rank(r)[0], -_item_rank(r)[1]))
    return items


# -------------- backtest (histórico, sin inventar señales que no existan) --------------
def reconstruct_signals(pick, series=None, pred=None):
    """Señales reconstruibles desde el historial (pFinal, movimiento, RLM). El resto queda sin dato."""
    cand = dict(market={"ml": "ML", "spread": "Spread", "total": "Total", "btts": "BTTS"}.get(pick.get("market"), pick.get("market")),
                side=pick.get("selection") or pick.get("side"),
                line=pick.get("line"), p_final=pick.get("p_final"), p_nv=pick.get("p_nv"),
                p_model=pick.get("p_model"), ev=pick.get("ev"), edge=pick.get("edge"),
                signals={})
    # splits → tickets/money
    if series:
        mk = {"ML": "ml", "Spread": "spread", "Total": "total"}.get(cand["market"] or "")
        side = cand["side"]
        pts = ((series.get("splits") or {}).get(mk) or {}).get(side) or []
        if pts:
            last = pts[-1]
            tickets = last[1] if len(last) > 1 else None
            money = last[2] if len(last) > 2 else None
            cand["signals"] = dict(tickets=tickets, money=money)
        # movement: first vs last odds
        books = ((series.get("lines") or {}).get(mk) or {})
        snaps = []
        for book, sides in books.items():
            for p in (sides or {}).get(side) or []:
                if p and p[2] is not None:
                    snaps.append(dict(t=int(p[0] * 1000), odds=int(p[2]), line=p[1], book=book))
        if len(snaps) >= 2:
            snaps.sort(key=lambda s: s["t"])
            try:
                dpp = CORE.move_pp(snaps[0]["odds"], snaps[-1]["odds"])
            except Exception:
                dpp = None
            mv = {}
            if cand["market"] == "ML":
                mv["ml"] = {side: dict(open=snaps[0]["odds"], cur=snaps[-1]["odds"], d_nv_pp=dpp)}
            out_mv = dict(market=dict(movement=mv, history=series, splits=series.get("splits")))
        else:
            out_mv = dict(market=dict(history=series, splits=(series or {}).get("splits")))
    else:
        out_mv = dict(market={})
    # consistencia con predicción guardada
    if pred and not consistent_with_pred(pred, cand):
        # modelo en contra si pFinal del pick no es el ganador
        pass
    dummy = dict(game={}, teams={}, **out_mv)
    analysis = panel(dummy, cand, pred)
    return cand, analysis


def would_publish(pick, analysis, pred=None, min_present=MIN_PRESENT, min_agree=MIN_AGREE):
    cand = dict(ev=pick.get("ev"), status="PICK", p_final=pick.get("p_final"),
                market={"ml": "ML", "spread": "Spread", "total": "Total"}.get(pick.get("market"), pick.get("market")),
                side=pick.get("selection") or pick.get("side"), line=pick.get("line"))
    if pred and cand.get("market") in ("ML", "Spread") and not _main_side_ok(pred, cand):
        return False, "contradice la predicción (pFinal/ganador)"
    if pred and cand.get("market") in ("Total", "BTTS") and not consistent_with_pred(pred, cand):
        return False, "no es coherente con el marcador predicho"
    conf = dict(level=pick.get("conf_level"))
    # reuse publish_reason but with custom thresholds via a shallow copy of analysis check
    ev = cand.get("ev")
    level = conf.get("level")
    if ev is None:
        return False, "EV: sin dato"
    if ev <= 0:
        return False, "EV no positivo"
    if level not in CONF_OK:
        return False, f"confianza {level or 'sin dato'}"
    n_pres = (analysis or {}).get("n_present") or 0
    n_ag = (analysis or {}).get("n_agree") or 0
    if n_pres < min_present:
        return False, f"solo {n_pres} señales con dato"
    if n_ag < min_agree:
        return False, f"{n_ag}/{n_pres} a favor"
    return True, None
