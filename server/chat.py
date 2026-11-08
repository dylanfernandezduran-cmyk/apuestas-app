"""Chat IA de NRNM (pt90u). Responde SÓLO con datos reales de la app (picks, probabilidades, líneas, predicción, lesiones, props).
LLM opcional por variable de entorno (nunca en el repo): API compatible con OpenAI.
  NRNM_LLM_API_KEY (o GROQ_API_KEY / OPENAI_API_KEY)  · NRNM_LLM_BASE_URL (por defecto Groq) · NRNM_LLM_MODEL
Sin llave -> {"llm": false}: el frontend responde con su motor local (reglas sobre los mismos datos), que también funciona en GitHub Pages."""
import json, os, time
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

SYSTEM = ("Eres el asistente de NRNM, una app de análisis deportivo (paper trading, sin dinero real). Responde en español de México, breve y claro. "
          "Usa EXCLUSIVAMENTE los datos JSON del contexto (picks, probabilidades, líneas, predicciones, lesiones, props). Si algo no está en el contexto, di que no lo tienes; "
          "nunca inventes cuotas, líneas, porcentajes ni lesiones. Recomienda primero los picks con estado PICK y luego LEAN, ordenados por edge (PASS/SIN_LINEA no son recomendación). Nunca contradigas la predicción ni el pick registrado del juego; si no coinciden, dilo. No menciones ningún «filtro estricto». Cita la línea y la cuota tal como vienen. Recuerda que son estimaciones, no garantías. Sin emojis excesivos.")

def _pick_short(it):
    g = it.get("game") or {}; l = it.get("lean") or {}
    return dict(juego=f"{(g.get('away') or {}).get('name')} @ {(g.get('home') or {}).get('name')}", liga=g.get("league"), id=g.get("id"), fecha=g.get("date"), pick_principal=it.get("status") == "PICK",
                pick=l.get("label"), mercado=l.get("market"), linea=l.get("line"), cuota=l.get("price_txt"), prob_final=round(l["p_final"], 3) if l.get("p_final") is not None else None,
                edge_pp=round(l["edge"], 1) if l.get("edge") is not None else None, estado=it.get("status"), confianza=(it.get("confidence") or {}).get("level"))

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
    return dict(juego=f"{(g.get('away') or {}).get('name')} @ {(g.get('home') or {}).get('name')}", estado=g.get("state"), fecha=g.get("date"),
                prediccion=dict(marcador=p.get("score"), ganador=p.get("winner"), total=p.get("total"), handicap=p.get("spread"), ambos_anotan=p.get("btts")),
                lean=((a.get("picks") or {}).get("lean") or {}).get("label"), picks_registrados=rec, probabilidades=probs[:24], lesiones=inj)

async def answer(q, league=None, eid=None):
    key, base, model = _cfg()
    if not key: return dict(llm=False)
    from . import data
    ctx = {}
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
        txt = r.json()["choices"][0]["message"]["content"]
        return dict(llm=True, text=txt, model=model, ts=time.time())
    except Exception as e:
        return dict(llm=False, error=type(e).__name__)
