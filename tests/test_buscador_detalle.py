"""Buscador del Inicio (/api/search + UI) y detalle de juego limpio (acordeones cerrados, mercados en bloques)."""
import json, os, re, shutil, socket, subprocess, sys, time
import pytest
from server import search as S
from server.config import LEAGUES, SPORTS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = {f: open(os.path.join(ROOT, "static", f), encoding="utf-8").read() for f in ("app.js", "extras.js", "detalle.js", "style.css", "index.html", "sw.js")}

def T(i, name, short, logo=None): return dict(id=str(i), name=name, short=short, abbr=short, logo=logo)
def G(i, lg, sport, h, a, state="pre", date="2026-11-03T20:00Z", note=None):
    return dict(id=str(i), league=lg, league_name=LEAGUES[lg]["name"], sport=sport, home=h, away=a, state=state, status="", date=date, note=note)
GAMES = {
    "mex.1": [G(1, "mex.1", "futbol", T(1, "Necaxa", "NEC"), T(2, "Tijuana", "TIJ"))],
    "nfl": [G(2, "nfl", "nfl", T(3, "Seattle Seahawks", "SEA"), T(4, "Chicago Bears", "CHI"), state="in")],
    "atp": [G(3, "atp", "tenis", T(5, "Lorenzo Musetti", "MUS"), T(6, "Alexander Zverev", "ZVE"), note="Rolex Paris Masters · Round 2")],
}

def test_search_normaliza_y_busca_por_prefijo_de_palabra():
    assert S.norm("Atlético  de San-Luis") == "atletico de san luis"
    r = S.search("necaxa", GAMES, LEAGUES, SPORTS)
    assert [t["name"] for t in r["teams"]] == ["Necaxa"] and r["teams"][0]["opp"] == "TIJ" and r["games"][0]["id"] == "1"
    assert S.search("ab", {"x": [G(9, "mex.1", "futbol", T(9, "Elizabeth", "ELI"), T(8, "Zeta", "ZET"))]}, LEAGUES, SPORTS)["teams"] == []   # 'ab' no entra a mitad de palabra
    assert S.search("a", GAMES, LEAGUES, SPORTS)["games"] == []                                                       # mínimo 2 letras

def test_search_jugadores_ligas_y_torneos():
    r = S.search("muse", GAMES, LEAGUES, SPORTS)
    assert r["teams"][0]["name"] == "Lorenzo Musetti" and r["games"][0]["league"] == "atp"
    assert any(l["key"] == "mex.1" for l in S.search("liga mx", GAMES, LEAGUES, SPORTS)["leagues"])
    tor = S.search("rolex", GAMES, LEAGUES, SPORTS)["leagues"]
    assert tor and tor[0]["key"] == "atp" and tor[0]["name"] == "Rolex Paris Masters" and tor[0]["sub"].startswith("Torneo")
    assert any(l["sport"] == "tenis" for l in S.search("tenis", GAMES, LEAGUES, SPORTS)["leagues"]) and S.search("zzzz", GAMES, LEAGUES, SPORTS)["games"] == []

def test_search_en_vivo_primero_y_resultado_directo_antes_que_por_liga():
    g = dict(GAMES); g["nfl"] = GAMES["nfl"] + [G(7, "nfl", "nfl", T(7, "Chicago Cubs", "CUB"), T(8, "Bears Reserve", "BRS"), date="2026-11-01T20:00Z")]
    r = S.search("bears", g, LEAGUES, SPORTS)
    assert r["games"][0]["state"] == "in" and len(r["games"]) == 2

def test_api_search_endpoint(monkeypatch):
    from fastapi.testclient import TestClient
    from server import main, data
    async def fake(lg): return (GAMES.get(lg, []), 1.0)
    monkeypatch.setattr(data, "list_games", fake)
    c = TestClient(main.app)
    r = c.get("/api/search", params={"q": "seahawks"}).json()
    assert r["games"][0]["league"] == "nfl" and r["teams"][0]["name"] == "Seattle Seahawks"
    assert c.get("/api/search", params={"q": "x"}).json() == dict(q="x", leagues=[], teams=[], games=[])
    assert c.get("/api/search", params={"q": "y" * 80}).json()["games"] == []

def test_fuente_ui_buscador_y_detalle_limpio():
    ex, js, css = SRC["extras.js"], SRC["app.js"], SRC["style.css"]
    assert 'id="hm-search"' in ex and ex.index('id="hm-live"') < ex.index('id="hm-search"') < ex.index('id="hm-sp"') and "setTimeout(()=>run(q),250)" in ex and "AbortController" in ex
    assert re.search(r"\.srch input\{[^}]*font-size:16px", css)                                                      # sin zoom en iPhone
    dj = SRC["detalle.js"]
    for fn in ("function dPred", "function ds(", "function stadiumWidget", "function courtLive", "detailSections"):
        assert fn in dj
    assert "acc('🧠" not in js and "#app > .acc" not in css.split("Detalle premium (pt75u)")[-1]                  # sin acordeones en el detalle nuevo
    ds_ = dj[dj.index("function detailSections"):]
    assert ds_.index("dPred") < ds_.index("dRec") < ds_.index("dPicks") < ds_.index("dProps") < ds_.index("dProb") and "p.corners" in dj
    v = lambda f, n: re.search(rf"{n}\?v=(\d+)", SRC[f]).group(1)
    assert [v("index.html", n) for n in ("style.css", "detalle.js", "app.js", "extras.js", "props.js", "chat.js", "recdia.js", "ticket.js")] == [v("sw.js", n) for n in ("style.css", "detalle.js", "app.js", "extras.js", "props.js", "chat.js", "recdia.js", "ticket.js")] == ["22", "8", "19", "15", "2", "4", "2", "2"] and "shell-v23" in SRC["sw.js"]
    assert SRC["index.html"].index("detalle.js") < SRC["index.html"].index("/app.js")                                   # detalle.js define los globales antes de app.js

def _py_playwright():
    py = shutil.which("python3")
    if not py or not os.path.exists("/usr/bin/google-chrome"): return None
    return py if subprocess.run([py, "-c", "import playwright"], capture_output=True).returncode == 0 else None

@pytest.mark.skipif(_py_playwright() is None, reason="sin Playwright/Chrome")
def test_buscador_y_detalle_limpio_e2e():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: socket.create_connection(("127.0.0.1", port), 0.2).close(); break
            except OSError: time.sleep(0.2)
        r = subprocess.run([_py_playwright(), os.path.join(ROOT, "tests", "e2e_detalle.py"), str(port), "/usr/bin/google-chrome"], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr[-800:]
        o = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        srv.terminate()
    # buscador
    assert o["orden"] == ["hm-live", "hm-search", "hm-sp", "hm-picks"] and o["input_font"] >= 16 and o["oculto_al_inicio"] is True
    assert o["llamadas"] == ["roma"]                                                      # debounce: teclear 'roma' = 1 petición
    assert o["grupos"] == ["LIGAS Y TORNEOS", "EQUIPOS Y JUGADORES", "JUEGOS"] and o["corto_oculta"] is True
    assert o["hrefs"] == ["#/deporte/futbol/mex.1", "#/juego/ita.1/77", "#/juego/ita.1/77"] and o["tap_liga"] == "#/deporte/futbol/mex.1"
    assert o["juego_home_first"].startswith("Roma vs Lazio")
    # detalle premium: secciones .ds en orden fijo (Predicción NRNM primero), sin acordeones ni bordes, títulos compactos en mayúsculas
    ORDER = ["pred", "rec", "picks", "prob", "splits", "rlm", "move", "odds", "mkt", "players", "cmp", "pitch", "trd", "rcn", "lin", "inj", "wx", "h2h", "key", "mdl"]
    for k in ("soc", "nfl", "tenis"):
        d = o[k]
        assert d["keys"][0] == "pred" and d["accs"] == 0 and d["bordes"] == 0 and all(t == ["uppercase", True] for t in d["heads"])
    for k in ("soc", "nfl"):
        ks = [x for x in o[k]["keys"] if x in ORDER]
        assert ks == sorted(ks, key=ORDER.index) and o["orden_ok"][k] is True
    assert o["soc"]["nombres"] == ["Necaxa", "Tijuana"] and o["soc"]["bloques"][0] == "RESULTADO FINAL" and "DOBLE OPORTUNIDAD" in o["soc"]["bloques"]
    assert o["nfl"]["nombres"] == ["Chicago Bears", "Seattle Seahawks"] and o["nfl"]["bloques"] == ["GANADOR", "TOTAL DE PUNTOS", "HÁNDICAP (SPREAD)"]   # NFL: visitante primero
    assert o["tenis"]["nombres"] == ["Carlos Alcaraz", "Jannik Sinner"] and o["tenis_home_primero"][0] == "Carlos Alcaraz"                               # tenis: local primero
    # ⓘ, plegado y la lista de predicción (fútbol: ganador, marcador, total, córners, hándicap con su resumen compacto)
    assert (o["info_oculta"], o["info_abierta"], o["plegada"], o["pred_rows"]) == (True, True, True, 4)
    assert o["pred_soc"] == ["GANADOR", "MARCADOR EXACTO", "TOTAL DE GOLES", "CÓRNERS", "HÁNDICAP"] and len(o["pred_resumen"]) == 5 and o["pred_resumen"][2] == "Menos de 2.5 goles" and "córners" in o["pred_resumen"][3]
    # en vivo: cancha arriba y el estado (ⓘ, plegado, scroll) sobreviven al refresco
    assert o["marcador"] == "2–1" and o["cancha_arriba"] <= 3 and o["refrescos"] >= 2 and o["estado_tras_refresco"] == [True, True] and o["scroll"] == 150 and o["errores"] == []

@pytest.mark.skipif(_py_playwright() is None, reason="sin Playwright/Chrome")
def test_detalle_sin_desborde_a_375_390_430():
    """Ningún elemento ni texto del detalle (todas las secciones con ⓘ abiertos, mocks de pre/en vivo) sale del viewport ni de su tarjeta."""
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: socket.create_connection(("127.0.0.1", port), 0.2).close(); break
            except OSError: time.sleep(0.2)
        r = subprocess.run([_py_playwright(), os.path.join(ROOT, "tests", "e2e_overflow.py"), str(port), "/usr/bin/google-chrome"], capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, r.stderr[-800:]
        o = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        srv.terminate()
    assert o == {"375": [], "390": [], "430": []}, o

def test_prob_meta_no_usa_la_clase_de_la_marca_pm():
    css, dj = SRC["style.css"], SRC["detalle.js"]
    assert 'class="pbm"' in dj and 'class="pm"' not in dj and re.search(r"\.pb \.pbm\{[^}]*flex-wrap:wrap", css) and not re.search(r"(^|\n)\.pm\{", css)
