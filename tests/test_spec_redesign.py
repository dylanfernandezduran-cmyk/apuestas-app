"""Aceptación del rediseño: Kelly, detectores ≥3 pp, REVISAR, chat, nav, footer, paleta."""
import os, re, time
from server import stake as ST, lineas as LN, model as M, chat as CHAT

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def src(*parts):
    return open(os.path.join(ROOT, *parts), encoding="utf-8").read()


# ---- 1/4 Kelly y topes
def test_kelly_zero_when_no_edge():
    r = ST.quarter_kelly(0.50, -110, 10000)
    assert r and r["frac"] == 0 and r["stake"] == 0 and "EV no positivo" in (r["reason"] or "")

def test_kelly_quarter_and_pick_cap():
    # p=0.70 a -110 es un edge grande: 1/4 Kelly debería superar 2% y caparse
    r = ST.quarter_kelly(0.70, -110, 10000, unit_pct=1)
    assert r and r["capped"] and abs(r["frac"] - 0.02) < 1e-9
    assert r["stake"] == 200.0  # 2% de 10,000
    assert "tope 2% por pick" in (r["reason"] or "")
    assert r["units"] == 2.0  # 1u = 1% = 100

def test_kelly_daily_cap():
    r = ST.quarter_kelly(0.70, -110, 10000, daily_used_frac=0.075)
    assert r and r["capped"] and abs(r["frac"] - 0.005) < 1e-9
    assert "tope 8% de exposición diaria" in (r["reason"] or "")

def test_kelly_accepts_decimal_and_american():
    a = ST.quarter_kelly(0.60, -150, 5000)
    b = ST.quarter_kelly(0.60, 1 + 100/150, 5000)
    assert a and b and abs(a["frac"] - b["frac"]) < 1e-9

def test_kelly_missing_returns_none():
    assert ST.quarter_kelly(None, -110, 1000) is None
    assert ST.quarter_kelly(0.6, None, 1000) is None
    assert ST.quarter_kelly(0.6, -110, 0) is None


# ---- detectores: solo ≥ 3 pp; datos de prueba
def _pts(*pairs):
    """pairs: (offset_s, price) desde t0."""
    t0 = 1_700_000_000
    return [[t0 + off, None, price] for off, price in pairs]

def test_steam_requires_3pp_inside_60min():
    # -110 (~52.4%) a -130 (~56.5%) = ~4.1 pp en 20 min
    st = LN.steam_in_series(_pts((0, -110), (20 * 60, -130)))
    assert st and st["kind"] == "STEAM" and abs(st["pp"]) >= 3
    # ~1 pp no alerta
    no = LN.steam_in_series(_pts((0, -110), (20 * 60, -115)))
    assert no is None
    # ≥3 pp pero fuera de 60 min no es STEAM
    late = LN.steam_in_series(_pts((0, -110), (2 * 3600, -150)))
    assert late is None

def test_rlm_public_and_against():
    # público 60% tickets; línea del lado público empeora (prob baja ≥3 pp): -150 (~60%) a -110 (~52.4%)
    books = [_pts((0, -150), (3600, -110))]
    splits = [[1, 60, 55], [2, 62, 54]]
    r = LN.rlm_in_market(books, splits)
    assert r and r["kind"] == "RLM" and r["tickets"] >= 55 and r["pp"] <= -3
    # público < 55 no alerta
    assert LN.rlm_in_market(books, [[1, 40, 40]]) is None
    # movimiento a favor del público no es RLM
    fav = [_pts((0, -110), (3600, -150))]
    assert LN.rlm_in_market(fav, splits) is None

def test_rezagada_consensus_and_laggard():
    # consenso se mueve ~6 pp; BookC no se mueve
    by = {
        "A": _pts((0, -110), (3600, -140)),
        "B": _pts((0, -110), (3600, -138)),
        "C": _pts((0, -110), (3600, -110)),
    }
    rz = LN.rezagada_in_market(by)
    assert rz and rz["kind"] == "REZAGADA" and abs(rz["consensus_pp"]) >= 3
    assert any(x["book"] == "C" for x in rz["laggards"])
    # todos se mueven igual: no rezagada
    even = {k: _pts((0, -110), (3600, -140)) for k in "ABC"}
    assert LN.rezagada_in_market(even) is None

def test_detect_filters_sub_3pp():
    series = {
        "lines": {"ml": {"A": {"home": _pts((0, -110), (600, -115))}}},
        "splits": {},
        "n_points": 2,
    }
    assert LN.detect(series) == []


# ---- REVISAR por divergencia alta
def test_divergence_high_sets_revisar():
    c = dict(status="PICK", ev=8, edge=12, p=0.6, p_model=0.7, p_nv=0.55, divergence=12, divergence_high=True)
    M.apply_confidence([c], dict(level="Alta"))
    assert c["status"] == "REVISAR"
    assert c.get("flag") == "Divergencia alta"
    assert c.get("edge_display") in (None, 0) or c.get("downgraded")


# ---- chat: polish, disclaimer, chase, sections, no certeza
def test_chat_polish_bans_and_disclaimer():
    out = CHAT.polish("Este pick es seguro y está garantizado.", "¿quién gana?")
    assert "seguro" not in out.lower() and "garantizado" not in out.lower()
    assert "estimado" in out.lower()
    assert CHAT.DISCLAIMER in out

def test_chat_chase_warning():
    out = CHAT.polish("Mete más unidades.", "quiero recuperar lo perdido y doblar la apuesta")
    assert "No persigas las pérdidas" in out
    assert CHAT.DISCLAIMER in out

def test_chat_system_has_sections_and_no_certainty():
    s = CHAT.SYSTEM.lower()
    for sec in CHAT.SECTIONS:
        assert sec.lower() in s or sec in CHAT.SYSTEM
    assert "seguro" in s and "garantizado" in s  # mencionadas como prohibidas
    assert "nunca uses" in s


# ---- UI: nav, footer, paleta, emojis se conservan, rutas, ticket bar
def test_bottom_nav_and_footer_help():
    html = src("static", "index.html")
    css = src("static", "style.css")
    app = src("static", "app.js")
    for label in ("Picks", "Deportes", "Líneas", "Récord", "IA"):
        assert label in html
    assert 'id="bnav"' in html and 'href="#/lineas"' in html and 'id="nav-ia"' in html
    assert "juegosysorteos.gob.mx" in html and "800 911 2000" in html
    assert 'id="legal"' in html and "footer.legal,#legal{position:fixed" in css.replace(" ", "")
    # paleta exacta
    for hex_ in ("#0b0b0e", "#15151a", "#23232b", "#2a2a31", "#f4f4f5", "#a1a1aa",
                 "#e11d63", "#ff5c8d", "#2dd4bf", "#fbbf24", "#ff7aa2"):
        assert hex_ in css
    # emojis se conservan
    assert "🔥" in app and "🎟️" in src("static", "ticket.js")
    # rutas
    assert "h[0]==='lineas'" in app and "viewLineas" in app
    assert "viewPicks" in app and "h[0]==='picks'" in app
    assert "setNav('record')" in app and "viewInfo" in app
    # ticket bar
    assert 'id="tkbar"' in html and "function tkFab" in src("static", "ticket.js")
    assert "Pick oficial" in src("static", "ticket.js") and "No es pick oficial" in src("static", "ticket.js")
    assert "tope/estimado" in src("static", "ticket.js") or "estimado, tope" in src("static", "ticket.js")
    # detalle tabs
    det = src("static", "detalle.js")
    for tab in ("Mercados", "Líneas", "Props", "Alineaciones"):
        assert tab in det
    assert "dPred(d)" in det and "dRec(d)" in det
    # Método desde récord
    assert "Método" in src("static", "recdia.js") and "#/info" in src("static", "recdia.js")
    # chat bankroll + disclaimer
    ch = src("static", "chat.js")
    assert "ch-bk" in ch and "CH_DISC" in ch and "chPolish" in ch
    # arquitectura multi-archivo
    assert "lineas.js" in html and "app.js" in html and "chat.js" in html

def test_api_routes_wired():
    main = src("server", "main.py")
    assert '/api/lineas' in main and '/api/stake' in main
    assert "bankroll=br" in main or "bankroll" in main
