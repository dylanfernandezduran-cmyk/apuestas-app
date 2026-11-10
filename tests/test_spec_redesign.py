"""Aceptación del rediseño (spec sections 5-8): núcleo, estados, detector, UI, récord."""
import json, os, subprocess, shutil
from server import stake as ST, lineas as LN, model as M, chat as CHAT, core as CORE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def src(*parts):
    return open(os.path.join(ROOT, *parts), encoding="utf-8").read()


# ---- 1/4 Kelly y topes
def test_kelly_zero_when_no_edge():
    r = ST.quarter_kelly(0.50, -110, 10000)
    assert r and r["frac"] == 0 and r["stake"] == 0 and "EV no positivo" in (r["reason"] or "")

def test_kelly_quarter_and_pick_cap():
    r = ST.quarter_kelly(0.70, -110, 10000, unit_pct=1)
    assert r and r["capped"] and abs(r["frac"] - 0.02) < 1e-9
    assert r["stake"] == 200.0
    assert "tope 2% por pick" in (r["reason"] or "")
    assert r["units"] == 2.0

def test_kelly_daily_cap():
    r = ST.quarter_kelly(0.70, -110, 10000, daily_used_frac=0.075)
    assert r and r["capped"] and abs(r["frac"] - 0.005) < 1e-9
    assert "tope 8% de exposición diaria" in (r["reason"] or "")

def test_no_apostar_when_ev_le_0():
    assert CORE.ev(0.50, -110) < 0
    assert CORE.stake_pct(0.50, -110) == 0


# ---- pFinal n0=100, ±20 pp, pickState
def test_pfinal_weight_n0_100_and_clamp():
    # n=0 → 100% mercado; n=50 → w=0.25; n>=100 → w=0.5
    assert abs(CORE.p_final(0.70, 0.50, 0) - 0.50) < 1e-9
    mid = CORE.p_final(0.70, 0.50, 50)
    assert abs(mid - (0.25 * 0.70 + 0.75 * 0.50)) < 1e-9
    full = CORE.p_final(0.70, 0.50, 100)
    assert abs(full - (0.5 * 0.70 + 0.5 * 0.50)) < 1e-9
    # clamp ±20 pp: modelo 0.90 vs mercado 0.50 → recortado a 0.70
    clamped = CORE.p_final(0.90, 0.50, 100)
    assert abs(clamped - (0.5 * 0.70 + 0.5 * 0.50)) < 1e-9

def test_pick_state_thresholds():
    assert CORE.pick_state(4, 0.02, "Media", 5) == "PICK"
    assert CORE.pick_state(4, 0.02, "baja", 5) == "LEAN"
    assert CORE.pick_state(2, 0.01, "Alta", 3) == "LEAN"
    assert CORE.pick_state(0.5, 0.01, "Alta", 2) == "PASS"
    assert CORE.pick_state(8, 0.10, "Alta", 12) == "REVISAR"

def test_divergence_high_sets_revisar():
    c = dict(status="PICK", ev=8, edge=12, p=0.6, p_model=0.7, p_nv=0.55, divergence=12, divergence_high=True)
    M.apply_confidence([c], dict(level="Alta"))
    assert c["status"] == "REVISAR"
    assert c.get("flag") == "Divergencia alta"
    # PASS with high gap also becomes REVISAR
    p = dict(status="PASS", ev=-1, edge=0.5, divergence=15, divergence_high=True)
    M.apply_confidence([p], dict(level="Media"))
    assert p["status"] == "REVISAR"


# ---- detector sobre datos de muestra (spec §6 y §8)
def _snaps(books_moves, t0=1_700_000_000_000):
    """books_moves: {book: [(offset_min, odds), ...]}"""
    out = []
    for book, pts in books_moves.items():
        for off, odds in pts:
            out.append(dict(book=book, t=t0 + off * 60_000, odds=odds))
    return out

def test_detect_steam_rlm_rezagada_on_sample():
    # 4 casas se mueven ~5 pp en 30 min ( -110 ~52.4% → -130 ~56.5%)
    steam = _snaps({b: [(0, -110), (30, -130)] for b in ("Pinnacle", "FanDuel", "DraftKings", "BetMGM")})
    d = CORE.detect_moves(steam, pct_tickets=0.40)
    assert "STEAM" in d["tags"] and abs(d["ppConsensus"]) >= 3
    assert "RLM" in d["tags"]  # cons>3 y tickets 40% ≤ 45%
    # sin 3 casas alineadas no hay STEAM
    two = _snaps({b: [(0, -110), (30, -130)] for b in ("A", "B")})
    d2 = CORE.detect_moves(two)
    assert "STEAM" not in d2["tags"]
    # movimiento < 3 pp no es STEAM
    tiny = _snaps({b: [(0, -110), (30, -115)] for b in ("Pinnacle", "FanDuel", "DraftKings", "BetMGM")})
    assert "STEAM" not in CORE.detect_moves(tiny)["tags"]
    # REZAGADA: 3 casas a -130, BetRivers se queda en -108 (mejor precio / implícita más baja)
    lag = _snaps({
        "Pinnacle": [(0, -110), (30, -130)],
        "FanDuel": [(0, -110), (30, -130)],
        "DraftKings": [(0, -110), (30, -128)],
        "BetRivers": [(0, -110), (30, -108)],
    })
    d3 = CORE.detect_moves(lag, pct_tickets=None)
    assert "REZAGADA" in d3["tags"]
    assert any(x["book"] == "BetRivers" and x["odds"] == -108 for x in d3["laggards"])
    # RLM no se etiqueta si falta % tickets
    assert "RLM" not in d3["tags"]

def test_lineas_scan_sample_series_only_3pp():
    # historial sintético en forma series
    t0 = 1_700_000_000
    def pts(*pairs):
        return [[t0 + off, None, price] for off, price in pairs]
    series = {"lines": {"ml": {
        "Pinnacle": {"home": pts((0, -110), (1800, -130))},
        "FanDuel": {"home": pts((0, -110), (1800, -130))},
        "DraftKings": {"home": pts((0, -110), (1800, -130))},
        "BetRivers": {"home": pts((0, -110), (1800, -108))},
    }}, "splits": {}, "n_points": 8}
    al = LN.detect(series)
    assert al and abs(al[0]["pp"]) >= 3
    assert "STEAM" in al[0]["tags"] and any("REZAGADA" in t for t in al[0]["tags"])
    # sub-3pp no aparece
    small = {"lines": {"ml": {"A": {"home": pts((0, -110), (600, -115))}}}, "splits": {}, "n_points": 2}
    assert LN.detect(small) == []


# ---- JS ↔ Python parity of the core (spec §6)
def test_core_js_matches_python():
    node = shutil.which("node")
    if not node:
        return
    js = open(os.path.join(ROOT, "static", "nrnm-core.js"), encoding="utf-8").read()
    script = js + r"""
    const steam = [];
    for (const b of ['Pinnacle','FanDuel','DraftKings','BetMGM']) {
      steam.push({book:b,t:0,odds:-110},{book:b,t:30*60000,odds:-130});
    }
    const det = detectMoves(steam, {pctTickets:0.40});
    const out = {
      ev: ev(0.55, -110),
      pFinal0: pFinal(0.70, 0.50, 0),
      pFinal50: pFinal(0.70, 0.50, 50),
      pFinal100: pFinal(0.70, 0.50, 100),
      pFinalClamp: pFinal(0.90, 0.50, 100),
      statePick: pickState({edge:4, evVal:0.02, conf:'Media', gapPP:5}),
      stateRev: pickState({edge:8, evVal:0.1, conf:'Alta', gapPP:12}),
      parlay: parlay([{odds:-110,pModel:0.55},{odds:120,pModel:0.48}]),
      detTags: det.tags,
      detPP: det.ppConsensus
    };
    console.log(JSON.stringify(out));
    """
    raw = subprocess.check_output([node, "-e", script], text=True)
    jsout = json.loads(raw)
    assert abs(jsout["ev"] - CORE.ev(0.55, -110)) < 1e-9
    assert abs(jsout["pFinal0"] - CORE.p_final(0.70, 0.50, 0)) < 1e-9
    assert abs(jsout["pFinal50"] - CORE.p_final(0.70, 0.50, 50)) < 1e-9
    assert abs(jsout["pFinal100"] - CORE.p_final(0.70, 0.50, 100)) < 1e-9
    assert abs(jsout["pFinalClamp"] - CORE.p_final(0.90, 0.50, 100)) < 1e-9
    assert jsout["statePick"] == CORE.pick_state(4, 0.02, "Media", 5) == "PICK"
    assert jsout["stateRev"] == "REVISAR"
    pl = CORE.parlay([{"odds": -110, "pModel": 0.55}, {"odds": 120, "pModel": 0.48}])
    assert jsout["parlay"]["american"] == pl["american"]
    assert abs(jsout["parlay"]["evCap"] - pl["evCap"]) < 1e-9
    assert "STEAM" in jsout["detTags"] and "RLM" in jsout["detTags"]


# ---- chat
def test_chat_polish_bans_and_disclaimer():
    out = CHAT.polish("Este pick es seguro y está garantizado.", "¿quién gana?")
    assert "seguro" not in out.lower() and "garantizado" not in out.lower()
    assert "estimado" in out.lower()
    assert CHAT.DISCLAIMER in out

def test_chat_chase_warning():
    out = CHAT.polish("Mete más unidades.", "quiero recuperar lo perdido y doblar la apuesta")
    assert "No persigas las pérdidas" in out or "pausar" in out.lower() or "bajar" in out.lower()
    assert CHAT.DISCLAIMER in out

def test_chat_system_has_sections_and_no_certainty():
    s = CHAT.SYSTEM.lower()
    for sec in CHAT.SECTIONS:
        assert sec.lower() in s or sec in CHAT.SYSTEM
    assert "seguro" in s and "garantizado" in s
    assert "nunca digas" in s or "nunca uses" in s
    assert "tope" in s and "independ" in s


# ---- UI acceptance (spec §3, §4, §8)
def test_screens_nav_footer_tokens_and_copy():
    html, css, app = src("static", "index.html"), src("static", "style.css"), src("static", "app.js")
    rec, ch, tk, det = src("static","recdia.js"), src("static","chat.js"), src("static","ticket.js"), src("static","detalle.js")
    blob = html + app + rec + ch + tk + det
    for label in ("Inicio", "Picks", "Deportes", "Líneas"):
        assert label in html
    assert 'id="bnav"' in html and 'href="#/lineas"' in html
    bnav = html.split('id="bnav"',1)[1].split("</nav>",1)[0]
    assert "Récord" not in bnav and 'data-n="record"' not in bnav
    assert 'data-n="inicio"' in bnav and 'href="#/record"' in html
    assert "juegosysorteos.gob.mx" not in html and "Línea de la Vida" not in html and 'id="legal"' not in html
    assert "Paper trading / estimaciones, no garantía." in app
    assert "nav-ia" not in html and "aria-label" in html
    for hex_ in ("#000000", "#0d0d0d", "#FF1179", "#06AAC4", "#3C85F7", "#F5B942", "#e6ebf2"):
        assert hex_ in css
    for gone in ("#2A1E4D", "#5A3B8C", "#8B7CC7", "#C9C2E3", "#3A2A66"):
        assert gone not in css
    assert "--bg:#000000" in css and "--acc:#FF1179" in css
    assert "sp-card" in css and "sp-draw" in css and "background:#111" in css
    assert 'class="sp-card"' in html and "No Risk No Money" in html and "sp-tag" not in html
    assert "function marketBlocks" in app and "ob-pk" in app and "mkb-tog" in app
    assert "height:44px" in css and ".mkb-h" in css
    assert "--r-card:16px" in css and "--r-btn:12px" in css and "--r-chip:999px" in css
    assert "--nav-h:72px" in css or "72px" in css
    assert "Inter:wght@400;600;700;800" in html
    # emojis se conservan
    assert "🔥" in app and "🎟️" in src("static", "ticket.js")
    # rutas
    for frag in ("#/picks", "#/deportes", "#/lineas", "#/record", "#/ia", "#/metodo", "viewLineas", "viewPicks"):
        assert frag in blob
    # chips
    assert "Alta confianza" in app and "Mejor pick de hoy" in app
    assert "Hoy no hay pick" in app
    assert "Divergencia alta: modelo" in app
    assert "Agregar al ticket" in app
    # Deportes
    assert "En vivo ahora" in app
    # IA
    ch = src("static", "chat.js")
    assert "Analista NRNM · datos reales" in ch
    assert "Props NBA" in ch and "Alineaciones" in ch and "Armar ticket" in ch
    # Método
    assert "Probabilidad final" in app and "Edge y EV" in app and "Casas y consenso" in app
    assert "RLM y dinero" in app and "Confianza" in app
    assert "no ve lesiones de último minuto ni descansos" in app
    # Ticket
    tk = src("static", "ticket.js")
    assert "Pick oficial" in tk and "No es pick oficial" in tk
    assert "Vaciar" in tk and "Guardar ticket" in tk
    assert "tkn" in tk
    assert "supone independencia y acumula el error del modelo" in tk
    assert "EV por 1u (tope)" in tk
    assert "Ticket ·" in tk and ">Ver<" in tk or "Ver</button>" in tk
    # detalle tabs + Mi pick
    det = src("static", "detalle.js")
    for tab in ("Mercados", "Líneas", "Props", "Alineaciones"):
        assert tab in det
    assert "compra el mejor" in det
    # IA es botón flotante (no vive en el nav); la nav es una píldora flotante
    assert "display:flex !important" in css and "#chb" in css
    assert "border-radius:999px" in css and "backdrop-filter" in css
    assert 'data-n="inicio"' in html and 'aria-label="Inicio"' in html
    # core loaded
    assert "nrnm-core.js" in html

def test_revisar_is_not_featured():
    app = src("static", "app.js")
    # el destacado excluye REVISAR
    assert "status!=='REVISAR'" in app or 'status!=="REVISAR"' in app
    assert "featOf" in app

def test_ev_helper_used_on_cards():
    app = src("static", "app.js")
    assert "function evPct" in app and "ev(p, l.price)" in app or "ev(p,l.price)" in app

def test_record_segments_and_clv():
    rec = src("static", "recdia.js")
    assert "Pick principal" in rec and "Sugerencias" in rec and "Todos" in rec
    assert "CLV" in rec
    assert "Hoy" in rec
    assert "Momio" in rec and "cierre" in rec
