"""Chat IA de NRNM (pt90u). Responde SÓLO con datos reales de la app (picks, probabilidades, líneas, predicción, lesiones, props).
LLM opcional por variable de entorno (nunca en el repo): API compatible con OpenAI.
  NRNM_LLM_API_KEY (o GROQ_API_KEY / OPENAI_API_KEY)  · NRNM_LLM_BASE_URL (por defecto Groq) · NRNM_LLM_MODEL
Sin llave -> {"llm": false}: el frontend responde con su motor local (reglas sobre los mismos datos), que también funciona en GitHub Pages."""
import json, os, re, time
import httpx

def _cfg():
    key = os.environ.get("NRNM_LLM_API_KEY") or os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if os.environ.get("NRNM_LLM_BASE_URL"): base = os.environ["NRNM_LLM_BASE_URL"]
    elif os.environ.get("NRNM_LLM_API_KEY") or os.environ.get("GROQ_API_KEY"): base = "https://api.groq.com/openai/v1"
    else: base = "https://api.openai.com/v1"
    model = os.environ.get("NRNM_LLM_MODEL") or ("llama-3.3-70b-versatile" if "groq" in base else "gpt-4o-mini")
    return key, base.rstrip("/"), model

def status():
    key, base, model = _cfg()
    return dict(llm=bool(key), provider=("groq" if "groq" in base else "openai-compatible") if key else None, model=model if key else None)

DISCLAIMER = "Estimación del modelo, no garantía de ganancia."
CHASE_WARN = "No persigas las pérdidas: subir la apuesta para recuperar no mejora el valor esperado y aumenta el riesgo de ruina."
BANNED_RE = re.compile(r"\b(seguro|segura|seguros|seguras|garantizado|garantizada|garantizados|garantizadas)\b", re.I)
CHASE_RE = re.compile(r"recuper(ar|o|ando)|perdid|cazar|perseguir|aument(ar|o|ando) la apuesta|doblar (la )?apuesta|all-?in", re.I)
SECTIONS = ("Mi pick", "Cuánto meterle", "Análisis a detalle", "Lesiones y alineaciones", "Localía y props")

SYSTEM = (
    "Eres el analista de NRNM. Responde en español, directo y con detalle. "
    "Recibes un JSON con los datos del juego (o del recorte de la app). Reglas:\n"
    "1. Usa solo cifras del JSON. Si falta un dato, dilo. Nunca inventes cuotas, líneas, porcentajes ni lesiones.\n"
    "2. Cada recomendación incluye: pick, cuota y casa, probabilidad del modelo, EV, "
    "cuota mínima aceptable, stake en unidades y en % del bankroll (1/4 Kelly, tope 2%) "
    "y en dinero si hay bankroll.\n"
    "3. Si EV <= 0, hay divergencia alta con el mercado o la alineación no está confirmada, di \"no apostar\" o \"esperar\" y explica por qué. REVISAR no se promociona como pick.\n"
    "4. Cubre siempre, en este orden de secciones: Mi pick; Cuánto meterle; Análisis a detalle; Lesiones y alineaciones; Localía y props. En Análisis a detalle recorre las 6 señales (modelo/pFinal, movimiento de línea, RLM/%apuestas/%dinero, tendencias, lesiones/alineaciones, físico/clima) con las cifras del JSON o «sin dato». No inventes. Un pick principal publicado ya pasó el filtro (≥4 señales con dato y ≥4 a favor, EV>0, confianza Media/Alta, mismo lado que la Predicción NRNM). PASS no se recomienda.\n"
    "5. Nunca digas \"seguro\", \"garantizado\" ni \"100%\". Cierra con: \"Estimación del modelo, no garantía de ganancia.\" No eres asesor financiero.\n"
    "6. En parlays avisa que el EV es un tope y que las piernas no son independientes.\n"
    "7. Si la persona parece perseguir pérdidas o subir el stake por encima de lo planeado, sugiere pausar y bajar el monto.\n"
    "Sólo llama «pick» o «recomendación» a lo que tenga aprobado=true (pasó TODOS los candados). Si aprobado=false, preséntalo como «Lado del modelo», con su EV y el motivo_bloqueo; nunca como recomendación. Días sin picks aprobados son válidos.\n"
    "Nunca contradigas la predicción ni el pick registrado del juego. Recomienda primero PICK y luego LEAN. PASS/SIN_LINEA no son recomendación. No menciones ningún «filtro estricto».\n"
    "8. El ganador del juego es consistencia.ganador_pfinal (mismo pFinal de la carta). "
    "El pFinal del pick (hándicap/total) NO es el ganador. Si consistencia.contradicciones no está vacío, dilo y quédate con la predicción. "
    "Si el estado es PASS o el EV≤0, no recomiendes y no hables de confianza Alta (la confianza mostrada es «no aplica»).\n"
    "9. Si piden los picks que concuerdan/coinciden con la predicción y los registrados, usa SOLO el arreglo "
    "picks_que_concuerdan (si viene). No inventes ninguno. Si está vacío, dilo. Recuerda que coincidir no garantiza acierto."
)

def polish(text, question=""):
    """Quita claims de certeza, añade aviso de perseguir pérdidas si aplica, y cierra con el disclaimer."""
    text = BANNED_RE.sub("estimado", text or "")
    if CHASE_RE.search(question or "") and "no persigas las pérdidas" not in text.lower():
        text = text.rstrip() + "\n\n" + CHASE_WARN
    if "no una garantía" not in text.lower() and "no es una garantía" not in text.lower() and "no garantía de ganancia" not in text.lower():
        text = text.rstrip() + "\n\n" + DISCLAIMER
    return text

def _pick_short(it):
    g = it.get("game") or {}; l = it.get("lean") or {}
    try:
        from .consistency import clamp_display_confidence
        conf = clamp_display_confidence(it.get("confidence"), it.get("status"), l.get("ev"))
        conf_level = conf.get("level")
    except Exception:
        conf_level = (it.get("confidence") or {}).get("level")
    return dict(juego=f"{(g.get('away') or {}).get('name')} @ {(g.get('home') or {}).get('name')}", liga=g.get("league"), id=g.get("id"), fecha=g.get("date"), pick_principal=it.get("status") == "PICK" and bool(it.get("approved")), aprobado=bool(it.get("approved")), motivo_bloqueo=it.get("block_reason"),
                pick=l.get("label"), mercado=l.get("market"), linea=l.get("line"), cuota=l.get("price_txt"), prob_final=round(l["p_final"], 3) if l.get("p_final") is not None else None,
                edge_pp=round(l["edge"], 1) if l.get("edge") is not None else None, estado=it.get("status"), confianza=conf_level,
                publicado=bool(it.get("published")), motivo=it.get("discard_reason"))

def _game_short(a):
    if not a: return None
    g = a.get("game") or {}
    p = a.get("pred") or {}
    inj = {}
    for tid, rows in (a.get("injuries") or {}).items():
        inj[tid] = [dict(nombre=r.get("name"), estado=r.get("status")) for r in rows[:8]]
    rec = [dict(pick=r.get("label"), linea=r.get("line"), linea_apertura=r.get("open_line"), cuota=r.get("odds"), cuota_apertura=r.get("open_odds"), estado=r.get("status"), cambio=r.get("state"))
           for r in (a.get("record") or [])]
    probs = []
    for m in ((a.get("probs") or {}).get("markets") or []):
        for o in m.get("outcomes") or []:
            probs.append(dict(mercado=m.get("title"), lado=o.get("label"), p_modelo=o.get("p_model"), p_mercado=o.get("p_nv"), edge=o.get("edge"), cuota=(o.get("best") or {}).get("price_txt")))
    try:
        from .consistency import chat_consistency, clamp_display_confidence
        cons = chat_consistency(a)
        pk = a.get("picks") or {}
        conf_show = clamp_display_confidence(pk.get("confidence"), pk.get("status"), ((pk.get("lean") or {}).get("ev")))
    except Exception:
        cons, conf_show = None, None
    return dict(juego=f"{(g.get('away') or {}).get('name')} @ {(g.get('home') or {}).get('name')}", estado=g.get("state"), fecha=g.get("date"),
                prediccion=dict(marcador=p.get("score"), ganador=p.get("winner"), total=p.get("total"), handicap=p.get("spread"), ambos_anotan=p.get("btts")),
                lean=((a.get("picks") or {}).get("lean") or {}).get("label"),
                pick_publicado=bool((a.get("picks") or {}).get("published")),
                aprobado=bool((a.get("picks") or {}).get("approved")),
                motivo_bloqueo="; ".join(l.get("reason", "") for l in ((a.get("picks") or {}).get("locks") or [])) or None,
                motivo_descarte=((a.get("picks") or {}).get("discard_reason")),
                analisis_detalle=(a.get("analysis") or ((a.get("picks") or {}).get("analysis"))),
                consistencia=cons,
                confianza_mostrada=(conf_show or {}).get("level") if conf_show else ((a.get("picks") or {}).get("confidence") or {}).get("level"),
                picks_registrados=rec, probabilidades=probs[:24], lesiones=inj)

def agreeing_intent(q):
    """True si pide la lista de picks que coinciden con la Predicción NRNM."""
    s = (q or "").lower()
    # quita acentos
    import unicodedata
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    if re.search(r"picks que concuerdan|picks que coinciden", s):
        return True
    if re.search(r"concuerd", s) and re.search(r"predic|registr|pick", s):
        return True
    if re.search(r"coincid", s) and re.search(r"predic|registr", s):
        return True
    if re.search(r"prediccion y pick|pick y prediccion|prediccion con (los )?picks", s):
        return True
    return False


def agreeing_reply(now=None, date=None, include_live=True):
    from .consistency import agreeing_picks, format_agreeing_text, format_agreeing_html
    report = agreeing_picks(now=now, date=date, include_live=include_live)
    return dict(
        agreeing=True, llm=False,
        text=format_agreeing_text(report),
        html=format_agreeing_html(report),
        n=report["n"], date=report["date"], include_live=report["include_live"],
        items=report["items"], note=report["note"],
    )


async def answer(q, league=None, eid=None, bankroll=None, unit_pct=None, daily_used_frac=0):
    if agreeing_intent(q):
        return agreeing_reply()
    key, base, model = _cfg()
    if not key: return dict(llm=False)
    from . import data
    ctx = {}
    if bankroll is not None:
        ctx["bankroll"] = bankroll
        ctx["unit_pct"] = unit_pct if unit_pct is not None else 1.0
        ctx["daily_used_frac"] = daily_used_frac or 0
        ctx["stake_rule"] = "1/4 Kelly, tope 2% por pick y 8% de exposición diaria; 1u = unit_pct % de la bankroll"
    try:
        pk = await data.picks("24h"); ctx["picks_24h"] = [_pick_short(it) for it in (pk.get("items") or [])[:30]]
    except Exception: ctx["picks_24h"] = None
    if league and eid:
        try: ctx["juego_abierto"] = _game_short(await data.analyze(league, eid))
        except Exception: pass
    msgs = [dict(role="system", content=SYSTEM), dict(role="user", content=f"CONTEXTO (JSON):\n{json.dumps(ctx, ensure_ascii=False, default=str)[:24000]}\n\nPREGUNTA: {q[:800]}")]
    try:
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=dict(model=model, messages=msgs, temperature=0.2, max_tokens=700))
        if r.status_code != 200: return dict(llm=False, error=f"LLM HTTP {r.status_code}")
        txt = polish(r.json()["choices"][0]["message"]["content"], q)
        return dict(llm=True, text=txt, model=model, ts=time.time(), sections=list(SECTIONS), disclaimer=DISCLAIMER)
    except Exception as e:
        return dict(llm=False, error=type(e).__name__)
