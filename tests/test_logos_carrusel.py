"""Logos/fotos (proxy /api/img con caché y lista blanca, iniciales de respaldo) y carrusel de juegos en vivo del inicio."""
import asyncio, json, os, re, shutil, socket, subprocess, sys, time
import pytest
from fastapi.testclient import TestClient
from server import imgproxy as IMG, record as R, history, data
from server.main import app

ROOT = os.path.join(os.path.dirname(__file__), "..")
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 40
SRC = {n: open(os.path.join(ROOT, "static", n), encoding="utf-8").read() for n in ("app.js", "extras.js", "style.css", "index.html", "sw.js")}

@pytest.fixture
def img(tmp_path, monkeypatch):
    monkeypatch.setattr(IMG, "_dir", lambda: str(tmp_path))
    IMG._mem.clear(); IMG._neg.clear()
    calls = []
    async def fake(url, headers=None):
        calls.append(url)
        return (PNG, "image/png") if "bos.png" in url or "3764" in url else None
    monkeypatch.setattr(IMG, "fetch_bytes", fake)
    return calls

def test_validate_solo_imagenes_de_espn():
    ok = "https://a.espncdn.com/i/teamlogos/nba/500/bos.png"
    assert IMG.validate(ok) == ("a.espncdn.com", "/i/teamlogos/nba/500/bos.png")
    for bad in ("http://a.espncdn.com/i/x.png", "https://evil.com/i/x.png", "https://a.espncdn.com.evil.com/i/x.png", "https://a.espncdn.com/api/x.json",
                "https://a.espncdn.com/i/../etc/passwd.png", "https://user@a.espncdn.com/i/x.png", "https://a.espncdn.com:8080/i/x.png", "", "file:///etc/passwd", None):
        assert IMG.validate(bad) is None, bad

def test_ancho_se_ajusta_a_tamanos_permitidos():
    assert [IMG.clamp_w(x) for x in (10, 44, 60, 112, 500, "abc")] == [32, 48, 64, 96, 128, 64]
    assert "combiner/i?img=/i/teamlogos/nba/500/bos.png&w=48" in IMG.upstream_url("/i/teamlogos/nba/500/bos.png", 48)

def test_get_image_cachea_en_memoria_y_disco_y_recuerda_fallos(img, tmp_path):
    u = "https://a.espncdn.com/i/teamlogos/nba/500/bos.png"
    r = asyncio.run(IMG.get_image(u, 44)); assert r == (PNG, "image/png") and len(img) == 1
    asyncio.run(IMG.get_image(u, 44)); assert len(img) == 1                       # memoria
    IMG._mem.clear(); asyncio.run(IMG.get_image(u, 44)); assert len(img) == 1     # disco
    assert any(f.endswith(".png") for f in os.listdir(tmp_path))
    miss = "https://a.espncdn.com/i/headshots/tennis/players/full/7833.png"
    assert asyncio.run(IMG.get_image(miss, 64)) is None and len(img) == 2
    assert asyncio.run(IMG.get_image(miss, 64)) is None and len(img) == 2         # caché negativa: no martilla a ESPN
    assert asyncio.run(IMG.get_image("https://evil.com/i/x.png")) is None and len(img) == 2

def test_endpoint_api_img(img):
    c = TestClient(app)
    r = c.get("/api/img", params=dict(u="https://a.espncdn.com/i/teamlogos/nba/500/bos.png", w=44))
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and "max-age" in r.headers["cache-control"] and r.content == PNG
    assert c.get("/api/img", params=dict(u="https://evil.com/i/x.png")).status_code == 400
    assert c.get("/api/img", params=dict(u="https://a.espncdn.com/i/headshots/tennis/players/full/1.png")).status_code == 404

def test_fetch_bytes_respaldo_curl_si_403(monkeypatch):
    from server import cache
    class R_:
        status_code = 403; content = b""; headers = {}
    class C_:
        async def get(self, *a, **k): return R_()
    monkeypatch.setattr(cache, "client", lambda: C_())
    monkeypatch.setattr(cache, "_curl_until", 0.0)
    monkeypatch.setattr(cache, "_curl_raw", lambda url, h, accept="": PNG)
    assert asyncio.run(cache.fetch_bytes("https://a.espncdn.com/x.png")) == (PNG, "image/png")

def test_tenis_trae_foto_del_jugador():
    c = dict(id="3764", athlete=dict(displayName="Lorenzo Musetti", shortName="L. Musetti", flag=dict(href="https://a.espncdn.com/i/teamlogos/countries/500/ita.png", alt="Italy")), linescores=[])
    s = data._t_side(c, {})
    assert s["logo"] == "https://a.espncdn.com/i/headshots/tennis/players/full/3764.png" and s["flag"].endswith("ita.png") and s["country"] == "Italy"

def test_record_junta_logos_de_equipos(db):
    R.remember_logos("nba", [dict(home=dict(id="2", logo="https://a.espncdn.com/i/teamlogos/nba/500/bos.png"), away=dict(id="9", logo="https://a.espncdn.com/i/teamlogos/nba/500/mia.png"))])
    with history._lock:
        c = R._c()
        c.execute("INSERT INTO picks(sport,league,eid,start_ts,home,away,home_id,away_id,market,selection,status,type) VALUES ('nba','nba','1',1,'Boston','Miami','2','9','ml','home','GANADO','main')")
        c.execute("INSERT INTO picks(sport,league,eid,start_ts,home,away,home_id,away_id,market,selection,status,type) VALUES ('nba','nba','2',2,'Otro','Otro2','5','6','ml','home','GANADO','main')")
        c.commit()
    rows = {r["eid"]: r for r in R.query()}
    assert rows["1"]["home_logo"].endswith("bos.png") and rows["1"]["away_logo"].endswith("mia.png")
    assert rows["2"]["home_logo"] is None                                           # sin logo conocido -> iniciales en el frontend
    assert R.remember_logos("nba", [dict(home=dict(id="2", logo="https://a.espncdn.com/i/teamlogos/nba/500/bos.png"), away={})]) == 0   # sin cambios no reescribe

@pytest.mark.skipif(not shutil.which("node"), reason="sin node")
def test_helpers_de_logo_en_frontend():
    app = SRC["app.js"]
    names = ("isSoc", "homeFirst", "sides", "vsMark", "imgSrc", "initials", "badge", "matchup")
    pick = "\n".join(re.search(rf"^const {n} = .*(?:\n  .*)*$", app, re.M).group(0) for n in names)
    js = "const esc=s=>String(s??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));\n" + pick + """
const g={sport:'futbol',home:{name:'Newcastle United',short:'Newcastle',logo:'https://a.espncdn.com/i/teamlogos/soccer/500/361.png'},away:{name:'Everton',short:'Everton',logo:null}};
console.log(JSON.stringify({ini:[initials('Newcastle United'),initials('L. Darderi'),initials('Galatasaray'),initials(''),initials('Lucia Bronzetti (1)')],
 b:badge(g.home,22),n:badge(g.away,30),m:matchup(g,true),nba:matchup({sport:'nba',home:{name:'H'},away:{name:'A'}},true),
 ph:badge({name:'Lorenzo Musetti',logo:'https://a.espncdn.com/i/headshots/tennis/players/full/3764.png'},30)}))"""
    o = json.loads(subprocess.check_output(["node", "-e", js], text=True))
    assert o["ini"] == ["NU", "LD", "GA", "?", "LB"]
    assert 'class="tl"' in o["b"] and "/api/img?w=44&amp;u=" in o["b"] and 'loading="lazy"' in o["b"] and 'width="22" height="22"' in o["b"] and "onerror" in o["b"]
    assert 'class="tl ini"' in o["n"] and 'data-i="EV"' in o["n"] and "<img" not in o["n"]                        # sin imagen -> iniciales, mismo tamaño
    assert "tl ph" in o["ph"]                                                                                      # foto de jugador: recorte arriba
    assert o["m"].index("Newcastle") < o["m"].index("Everton") and o["nba"].index(">A<") < o["nba"].index(">H<")   # fútbol local primero; EE. UU. visitante @ local

def test_logos_y_carrusel_usados_en_toda_la_app():
    app, ex, css = SRC["app.js"], SRC["extras.js"], SRC["style.css"]
    assert "badge(t,22)" in app and "badge(t,56)" in app and "recMatch(r)" in app and "matchup(g)" in app           # tarjetas, héroe, récord, picks
    assert "badge(x,30)" in ex and "id=\"hm-rec\"" in ex                                                         # carrusel en vivo + récord en inicio (sin duplicar picks)
    assert "scroll-snap-type:x mandatory" in css and "scroll-snap-align:center" in css and ".car-dots" in css and ".tl.ini::after" in css
    assert "carPatch(lb," in ex and "data-gid" in ex and re.search(r"\.car-n.*textContent=`\$\{i\+1\}/\$\{n\}`", ex.replace("\n", " ")) is not None
    # versiones de caché subidas y el service worker apunta a las mismas
    v = lambda f, n: re.search(rf"{n}\?v=(\d+)", SRC[f]).group(1)
    assert [v("index.html", n) for n in ("style.css", "app.js")] == [v("sw.js", n) for n in ("style.css", "app.js")] and "extras.js?v=" + v("sw.js", "extras.js") in SRC["index.html"]

def _py_playwright():
    py = shutil.which("python3")
    if not py or not os.path.exists("/usr/bin/google-chrome"): return None
    return py if subprocess.run([py, "-c", "import playwright"], capture_output=True).returncode == 0 else None

@pytest.mark.skipif(_py_playwright() is None, reason="sin Playwright/Chrome")
def test_carrusel_e2e_una_tarjeta_deslizable_y_no_se_reinicia_al_refrescar():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: socket.create_connection(("127.0.0.1", port), 0.2).close(); break
            except OSError: time.sleep(0.2)
        r = subprocess.run([_py_playwright(), os.path.join(ROOT, "tests", "e2e_carrusel.py"), str(port), "/usr/bin/google-chrome"], capture_output=True, text=True, timeout=90)
        assert r.returncode == 0, r.stderr[-800:]
        o = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        srv.terminate()
    assert o["inicio"]["n"] == 5 and o["inicio"]["dots"] == 5 and o["inicio"]["txt"] == "1/5" and o["inicio"]["on"] == 0 and "mandatory" in o["inicio"]["vis"]
    assert o["tras_deslizar"]["txt"] == "4/5" and o["tras_deslizar"]["on"] == 3
    assert o["tras_refresco"]["txt"] == "4/5" and o["tras_refresco"]["on"] == 3          # el refresco de 25 s no devuelve a la primera
    assert o["marcador_antes"] != o["marcador_despues"]                                   # y sí actualizó el marcador en sitio
    assert o["iniciales"] >= 5 and o["errores"] == []                                     # imagen rota -> iniciales, sin errores JS


@pytest.mark.skipif(_py_playwright() is None, reason="sin Playwright/Chrome")
def test_layout_inicio_y_picks_por_deporte_e2e():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.main:app", "--port", str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: socket.create_connection(("127.0.0.1", port), 0.2).close(); break
            except OSError: time.sleep(0.2)
        r = subprocess.run([_py_playwright(), os.path.join(ROOT, "tests", "e2e_layout.py"), str(port), "/usr/bin/google-chrome"], capture_output=True, text=True, timeout=90)
        assert r.returncode == 0, r.stderr[-800:]
        o = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        srv.terminate()
    assert o["secciones"] == ["hm-live", "hm-search", "hm-sp", "hm-rec"]                          # en vivo -> búsqueda -> deportes -> récord (sin duplicar picks)
    rec_txt = o.get("hm_rec_text") or " ".join(o.get("texto_inicio_tiene") or [])
    assert "Récord" in rec_txt or "Record" in rec_txt                                      # resumen de récord en Inicio
    assert "Bajas confirmadas" not in (o.get("texto_inicio_tiene") or []) and "Bajas confirmadas" not in rec_txt
    assert o["nav"] == ["⚾ MLB", "🏈 NFL", "🏀 NBA", "🏒 NHL", "⚽ Fútbol", "🎾 Tenis"] or [x.replace("\n", " ") for x in o["nav"]] == ["⚾ MLB", "🏈 NFL", "🏀 NBA", "🏒 NHL", "⚽ Fútbol", "🎾 Tenis"]
    assert o["nav_href"] == [f"#/deporte/{k}" for k in ("mlb", "nfl", "nba", "nhl", "futbol", "tenis")] and o["tap_nfl"] == "#/deporte/nfl"
    assert o["nav_estilo"]["bw"] == "0px" and o["nav_estilo"]["bg"] in ("rgba(0, 0, 0, 0)", "transparent") and o["nav_estilo"]["sh"] == "none"   # sin cajas
    assert o["nav_vivo"] == ["nba"] and o["rec_tab"] is True                           # punto de "en vivo"; la pestaña Récord sigue
    assert o["grupos"] == ["mlb", "nfl", "futbol", "nba", "nhl", "tenis"]
    assert o["orden_cards"] == "H:mlb,c,c,H:nfl,c,H:futbol,c,c,H:nba,c,H:nhl,c,H:tenis,c"
    assert o["grupos_sin_vacios"] == ["mlb", "nba"] and o["errores"] == []
