"""Calidad de datos, incertidumbre y estado de validación de cada pick.

Estados: VALIDADO · INCIERTO · ESPERAR (alineaciones o lesiones sin confirmar) · PASAR (sin datos o sin valor).
Sólo usa lo que trae el análisis (ESPN, Action Network, Pinnacle, Open-Meteo). No inventa nada.
"""
from __future__ import annotations
import time

LAST: dict = {}     # (league, eid) -> {"dq": ..., "validation": ...} (lo lee el tablero de inicio)
OUTDOOR = {"football", "baseball", "soccer"}


def data_quality(a):
    g = a.get("game") or {}
    fam = a.get("_fam") or {"nba": "basketball", "nfl": "football", "nhl": "hockey", "mlb": "baseball", "futbol": "soccer", "tenis": "tennis"}.get(g.get("sport"), "")
    m = a.get("model") or {}
    checks = []
    def add(key, label, ok, weight, detail=None):
        checks.append(dict(key=key, label=label, ok=ok, weight=weight, detail=detail))
    add("odds", "Cuotas", bool(a.get("odds")), 25)
    mk = a.get("market") or {}
    add("splits", "% apuestas / % dinero", bool(mk.get("splits")), 10)
    add("books", "Comparador de casas", bool(mk), 5)
    samp = m.get("sample")
    add("sample", "Muestra del modelo", samp is not None and samp >= 0.75, 20, f"{round((samp or 0) * 100)}%" if samp is not None else None)
    if fam != "tennis":
        inj = a.get("injuries_full") or {}
        add("injuries", "Reporte de lesiones", bool(inj.get("supported")), 15)
        lu = (a.get("lineups") or {}).get("sides") or {}
        sts = [v.get("status") for v in lu.values()]
        conf = bool(sts) and all(s == "confirmado" for s in sts)
        proj = bool(sts) and all(s in ("confirmado", "proyectado", "profundidad") for s in sts)
        add("lineups", "Alineaciones", conf or proj, 15, "confirmadas" if conf else ("proyectadas" if proj else "sin publicar"))
    if fam in OUTDOOR:
        wx = a.get("weather") or {}
        add("weather", "Clima", wx.get("status") in ("ok", "techado", "retractil"), 10)
    tot = sum(c["weight"] for c in checks) or 1
    score = round(sum(c["weight"] for c in checks if c["ok"]) / tot * 100)
    # incertidumbre: desviación del margen (o total) ampliada si la muestra es corta
    unc = None
    if m.get("sigma"):
        unc = round(float(m["sigma"]) * (1 + (1 - min(1.0, samp or 0)) * 0.5), 2)
    level = "alta" if score >= 80 else ("media" if score >= 55 else "baja")
    return dict(score=score, level=level, checks=checks, sigma_eff=unc,
                missing=[c["label"] for c in checks if not c["ok"]])


def validate(a, dq=None):
    """Estado del pick principal (lean) del análisis."""
    dq = dq or data_quality(a)
    pk = a.get("picks") or {}
    lean = pk.get("lean") or {}
    g = a.get("game") or {}
    reasons = []
    if not lean or lean.get("price") is None:
        return dict(state="PASAR", reasons=["Sin cuota: sin cuota no es pick"])
    pb = pk.get("policy_block")
    if pb:
        return dict(state="INCIERTO" if pb.startswith("Auditor") else "PASAR", reasons=[pb])
    ev = lean.get("ev")
    if ev is None or ev <= 0:
        reasons.append(f"EV {ev:+.1f}% (sin valor)" if ev is not None else "EV sin dato")
        return dict(state="PASAR", reasons=reasons)
    if dq["score"] < 40:
        return dict(state="PASAR", reasons=[f"Datos insuficientes ({dq['score']}/100): falta " + ", ".join(dq["missing"])])
    # ESPERAR: alineación sin confirmar o lesión clave en duda, y faltan < 24 h
    lu = (a.get("lineups") or {}).get("sides") or {}
    unconfirmed = [s for s, v in lu.items() if v.get("status") in ("proyectado", "sin_publicar")]
    key_doubt = [k for k in ((a.get("model") or {}).get("key_injuries") or []) if any(w in k.lower() for w in ("quest", "doubt", "duda", "day-to-day", "día a día", "gtd"))]
    if key_doubt:
        reasons.append("Jugador clave en duda: " + ", ".join(key_doubt[:3]))
    if unconfirmed and g.get("sport") in ("nba", "nhl", "futbol", "mlb"):
        reasons.append("Alineación sin confirmar")
    if reasons:
        return dict(state="ESPERAR", reasons=reasons)
    if lean.get("divergence_high"):
        return dict(state="INCIERTO", reasons=["Divergencia alta modelo vs mercado (>10 pp)"])
    if dq["score"] < 70:
        return dict(state="INCIERTO", reasons=[f"Calidad de datos {dq['score']}/100: falta " + ", ".join(dq["missing"])])
    conf = (pk.get("confidence") or {}).get("level")
    if conf not in ("Alta", "Media"):
        return dict(state="INCIERTO", reasons=[f"Confianza {conf or 'sin dato'}"])
    return dict(state="VALIDADO", reasons=[f"EV {ev:+.1f}%, datos {dq['score']}/100, confianza {conf}"])


def _approve(a, dq):
    """picks.approved = el pick principal pasa TODOS los candados (server/policy.py). Sólo entonces la UI dice «PICK»."""
    pk = a.get("picks") or {}; lean = pk.get("lean") or {}
    if not pk: return
    if not lean or not pk.get("published"):
        pk["approved"] = False
        pk["locks"] = [dict(key="consistency" if lean else "value", label="Publicación",
                            reason=pk.get("policy_block") or pk.get("discard_reason") or "Sin pick publicado")]
        return
    from . import policy as POL, consistency as CS
    from .record import MKT
    g = a.get("game") or {}
    it = dict(p_final=lean.get("p_final"), ev_pct=lean.get("ev"), sport=g.get("sport"), market=MKT.get(lean.get("market"), str(lean.get("market") or "").lower()),
              live=g.get("state") not in (None, "pre"), divergence_high=lean.get("divergence_high"))
    c = POL.check(it, POL.history(CS._rows), dq=dq.get("score"))
    if lean.get("divergence_high"):
        c["locks"].append(dict(key="consistency", label="Consistencia", reason="Divergencia alta modelo vs mercado (>10 pp)")); c["approved"] = False
    pk["approved"] = c["approved"]; pk["locks"] = c["locks"]; pk["tier"] = c["tier"]


def attach(a, league, eid):
    try:
        dq = data_quality(a)
        v = validate(a, dq)
        a["data_quality"] = dq; a["validation"] = v
        _approve(a, dq)
        LAST[(league, str(eid))] = dict(dq=dq, validation=v, lean=((a.get("picks") or {}).get("lean") or {}).get("label"), ts=time.time())
    except Exception:
        pass
    return a
