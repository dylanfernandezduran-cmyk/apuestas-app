"""Buscador del Inicio (/api/search + UI) y detalle de juego limpio (acordeones cerrados, mercados en bloques)."""
import json, os, re, shutil, socket, subprocess, sys, time
import pytest
from server import search as S
from server.config import LEAGUES, SPORTS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = {f: open(os.path.join(ROOT, "static", f), encoding="utf-8").read() for f in ("app.js", "extras.js", "style.css", "index.html", "sw.js")}

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
    for fn in ("mainPickCard", "marketBlocks", "heroMid", "acc("):
        assert fn in js
    assert "acc('🧠 Análisis del modelo'" in js and "acc('💱 Cuotas y movimiento de línea'" in js and "acc('🩺 Alineaciones, bajas y clima'" in js
    assert "if(!matchMedia('(max-width:640px)').matches) return;" not in js                                         # acordeones también en escritorio
    v = lambda f, n: re.search(rf"{n}\?v=(\d+)", SRC[f]).group(1)
    assert [v("index.html", n) for n in ("style.css", "app.js", "extras.js")] == [v("sw.js", n) for n in ("style.css", "app.js", "extras.js")] == ["13", "12", "11"] and "shell-v15" in SRC["sw.js"]

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
    # detalle: encabezado -> pick -> mercados -> acordeones, todos cerrados
    for k in ("soc", "nfl"):
        d = o[k]
        assert d["top"][:3] == ["hero", "pick", "mercados"] and set(d["top"][3:]) == {"acc"}
        assert all(c for _, c in d["accs"]) and d["visibles_acc_body"] == 0 and d["notas_visibles"] == 0
        assert len(d["pick"]) == 1 and all(n >= 2 for n in d["botones"])
    assert o["soc"]["nombres"] == ["Necaxa", "Tijuana"] and o["soc"]["botones"] == [3, 2, 2, 3] and o["soc"]["bloques"][0] == "RESULTADO FINAL" and "DOBLE OPORTUNIDAD" in o["soc"]["bloques"]
    assert o["nfl"]["nombres"] == ["Chicago Bears", "Seattle Seahawks"] and o["nfl"]["bloques"] == ["GANADOR", "TOTAL DE PUNTOS", "HÁNDICAP (SPREAD)"]   # NFL: visitante primero
    assert o["soc"]["h"] < 2000 and o["nfl"]["h"] < 2000
    # en vivo: marcador al centro, "En vivo" abierto, el acordeón abierto por el usuario y el scroll sobreviven al refresco
    assert o["en_vivo_abierto"][0].startswith("📡 En vivo") and len(o["en_vivo_abierto"]) == 1 and o["marcador"] == "1 – 0"
    assert o["refrescos"] >= 2 and o["abierto_tras_refresco"] == [False, True, False, False, False, False] and o["scroll"] == 150 and o["errores"] == []
