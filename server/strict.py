"""Picks ESTRICTOS y coherentes (pt9x, Dylan): una sola vista del modelo por juego.

Puntaje compuesto 0-100 de cada candidato (pesos documentados, también en /info):
  · Edge vs mercado sin vig ........ 35  (lineal hasta 8 pp)
  · Probabilidad final del modelo .. 25  (lineal de 50 % a 70 %)
  · Señales de mercado ............. 15  (RLM / dinero > tickets a favor 15 · neutral o sin dato 7 · mixto 5 · en contra 0)
  · Confianza del modelo ........... 15  (Alta 15 · Media 9 · Baja 3: muestra, modelo vs mercado, lesiones, abridores)
  · Contexto ....................... 10  (−5 viento ≥ 25 mph en un Over al aire libre; −10 si falta un dato crítico)
  Forma reciente, H2H, descanso y local/visita entran vía las calificaciones del modelo (no se cuentan dos veces).

Filtros duros (si falla uno NO es pick oficial):
  · edge ≥ 2.0 pp y probabilidad final ≥ 55 %  (umbrales elegidos con el récord real calificado)
  · puntaje compuesto ≥ 60 (extra conservador: las señales no se guardaban en el récord, así que este corte no está backtesteado)
  · las señales de mercado no van en contra (RLM / dinero grande del otro lado)
  · sin jugador clave en duda (lesionado no "probable") ni abridor de MLB sin confirmar
  · el lado coincide con la Predicción NRNM (se revisa después de construirla)
Máximo 1 pick oficial por juego; un 2.º sólo si es de otro tipo de mercado (lado + total), ambos ≥ 75 puntos y no se contradicen.
Todo lo demás con edge > 0 que coincide con la predicción queda como «También considerado» (no recomendado, no se registra)."""

import os
# Modo estricto APAGADO por defecto (pt98: Dylan pidió regresar a los picks anteriores). Encender con NRNM_STRICT=1.
ENABLED = os.environ.get("NRNM_STRICT", "0") == "1"

EDGE_MIN, P_MIN, SCORE_MIN, SECOND_MIN = 2.0, 0.55, 60, 75
SIG_PTS = {"a_favor": 15, "neutral": 7, "sin_dato": 7, "mixto": 5, "en_contra": 0}
CONF_PTS = {"Alta": 15, "Media": 9, "Baja": 3}
KIND = {"ML": "lado", "Spread": "lado", "BTTS": "btts", "Total": "total"}

def _clamp(x): return max(0.0, min(1.0, x))

def score(c, conf_level, ctx):
    e = c.get("edge"); p = c.get("p_final")
    if e is None or p is None: return 0, {}
    v = (c.get("signals") or {}).get("verdict") or "sin_dato"
    parts = dict(edge=round(35 * _clamp(e / 8.0), 1), prob=round(25 * _clamp((p - 0.5) / 0.2), 1), señales=SIG_PTS.get(v, 7),
                 confianza=CONF_PTS.get(conf_level, 3), contexto=10)
    if ctx.get("windy") and c.get("market") == "Total" and c.get("side") == "over": parts["contexto"] -= 5
    if ctx.get("critical_missing"): parts["contexto"] -= 10
    return round(sum(parts.values())), parts

def gates(c, ctx):
    why = []
    if c.get("edge") is None: why.append("sin línea")
    elif c["edge"] < EDGE_MIN: why.append(f"edge {c['edge']:.1f} pp < {EDGE_MIN:g}")
    if (c.get("p_final") or 0) < P_MIN: why.append(f"prob. {100 * (c.get('p_final') or 0):.0f}% < {100 * P_MIN:.0f}%")
    if ((c.get("signals") or {}).get("verdict")) == "en_contra": why.append("señales de mercado en contra")
    if ctx.get("key_injury"): why.append("jugador clave en duda")
    if ctx.get("critical_missing"): why.append(ctx["critical_missing"])
    if not why and (c.get("score") or 0) < SCORE_MIN: why.append(f"puntaje {c.get('score')}/100 < {SCORE_MIN}")
    return why

def apply(picks, ctx):
    """Marca score/gates/official en los candidatos y deja picks['official'] (0-2) y picks['considered']. Cambia lean/status."""
    if not picks: return picks
    lvl = (picks.get("confidence") or {}).get("level")
    cands = picks.get("candidates") or []
    for c in cands:
        c["score"], c["score_parts"] = score(c, lvl, ctx)
        c["why_not"] = gates(c, ctx)
    ok = sorted([c for c in cands if not c["why_not"]], key=lambda c: -c["score"])
    off = ok[:1]
    if off:
        sec = next((c for c in ok[1:] if KIND.get(c["market"]) != KIND.get(off[0]["market"]) and c["score"] >= SECOND_MIN and off[0]["score"] >= SECOND_MIN), None)
        if sec: off.append(sec)
    _set(picks, off)
    return picks

def _set(picks, off):
    for c in picks.get("candidates") or []:
        c["official"] = any(c is o for o in off)
        if not c["official"] and c.get("status") == "PICK": c["status"] = "LEAN"     # ya no es pick: sólo considerado
    picks["official"] = off
    if off: picks["lean"] = off[0]; picks["status"] = "PICK"
    else:
        best = next((c for c in sorted(picks.get("candidates") or [], key=lambda c: -(c.get("score") or 0)) if c.get("edge") is not None), None)
        picks["lean"] = best; picks["status"] = "PASS" if best else "SIN_LINEA"
    picks["strict"] = dict(edge_min=EDGE_MIN, p_min=P_MIN, score_min=SCORE_MIN, second_min=SECOND_MIN)

def pred_side(pred, market):
    if not pred: return None
    if market == "ML": return (pred.get("winner") or {}).get("side")
    return (pred.get({"Spread": "spread", "Total": "total", "BTTS": "btts"}.get(market, "")) or {}).get("side")

def finalize(picks, pred):
    """Después de la Predicción NRNM: quita oficiales que la contradigan y arma «También considerado» (sólo lados que coinciden)."""
    if not picks: return picks
    off = []
    for c in picks.get("official") or []:
        s = pred_side(pred, c["market"])
        if s is not None and s != c["side"]:
            c.setdefault("why_not", []).append("contradice la Predicción NRNM")
        else: off.append(c)
    if len(off) != len(picks.get("official") or []): _set(picks, off)
    cons = []
    for c in picks.get("candidates") or []:
        if c.get("official") or c.get("edge") is None or c["edge"] <= 0: continue
        s = pred_side(pred, c["market"])
        if s is not None and s != c["side"]: continue
        cons.append(c)
    picks["considered"] = sorted(cons, key=lambda c: -(c.get("score") or 0))[:3]
    if picks.get("lean") is not None and not picks.get("official"):
        s = pred_side(pred, picks["lean"]["market"])
        if s is not None and s != picks["lean"]["side"]:     # el «mejor» mostrado tampoco puede contradecir la predicción
            picks["lean"] = picks["considered"][0] if picks["considered"] else None
            if picks["lean"] is None: picks["status"] = "PASS"
    return picks
