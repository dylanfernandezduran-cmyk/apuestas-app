"""Predicción NRNM: construcción (fútbol/margen/tenis), líneas de mercado vs del modelo, córners con datos reales, bloqueo al inicio, calificación y estadísticas."""
import asyncio, copy, json
from datetime import datetime, timezone
import pytest
from conftest import fixture
from server import prediction as P, model as M

NOW = 1_800_000_000
iso = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

def soc_model(lh=1.9, la=.8):
    pm = lambda l: M.pois_pmf(l, 12)
    mat = [[pm(lh)[i] * pm(la)[j] for j in range(13)] for i in range(13)]; z = sum(map(sum, mat)); mat = [[x / z for x in r] for r in mat]
    ph = sum(mat[i][j] for i in range(13) for j in range(13) if i > j); pd = sum(mat[i][i] for i in range(13))
    return dict(lam_home=lh, lam_away=la, p_home=ph, p_draw=pd, p_away=1 - ph - pd,
                total=lambda t: M.cover_matrix(mat, lambda i, j: i + j, t), cover=lambda t: M.cover_matrix(mat, lambda i, j: i - j, t))

COR = dict(home=5.8, away=4.1, total=9.9, line=9.5, sd=3.4, n=[6, 6])

def game(start=NOW + 3600, state="pre", eid="1", sport="futbol", league="mex.1"):
    return dict(sport=sport, league=league, id=eid, state=state, date=iso(start), home=dict(id="1", name="León"), away=dict(id="2", name="América"))

def test_futbol_sin_mercado_usa_lineas_del_modelo_y_marca_su_origen():
    p = P.build(game(), soc_model(), None, "soccer")
    assert p["winner"]["side"] == "home" and p["score"]["home"] > p["score"]["away"]          # el marcador es coherente con el ganador
    assert p["total"]["line"] == 2.5 and p["total"]["line_src"] == "modelo" and p["total"]["side"] in ("over", "under")
    assert p["spread"]["line_src"] == "modelo" and p["spread"]["line"] in (-1.5, -0.5) and p["spread"]["side"] == "home" and p["spread"]["p"] >= .5
    assert "corners" not in p                                                                  # sin datos reales de córners no hay fila

def test_futbol_visitante_favorito_hándicap_en_linea_del_local():
    p = P.build(game(), soc_model(.6, 2.2), None, "soccer")
    assert p["winner"]["side"] == "away" and p["spread"]["side"] == "away" and p["spread"]["line"] in (1.5, .5)

def test_mercado_prevalece_sobre_la_linea_del_modelo():
    p = P.build(game(), soc_model(), dict(total=dict(over=dict(line=3.5)), spread=dict(home=dict(line=-1.5)), book="X"), "soccer")
    assert p["total"]["line"] == 3.5 and p["total"]["line_src"] == "mercado" and p["spread"]["line"] == -1.5 and p["spread"]["line_src"] == "mercado"

def test_corners_solo_con_datos_reales():
    p = P.build(game(), soc_model(), None, "soccer", COR)
    c = p["corners"]
    assert c["line"] == 9.5 and c["side"] == "over" and 0.5 < c["p"] < 1 and c["label"] == "Más de 9.5 córners" and c["n"] == [6, 6]
    assert P.build(game(), soc_model(), None, "soccer", None).get("corners") is None
    # otros deportes jamás llevan córners
    mm = dict(mu=3.0, sigma=13.0, exp_total=44.5, tsigma=10.0, p_home=.6, p_away=.4, total=lambda t: M.cover_normal(44.5, 10, t), cover=lambda t: M.cover_normal(3, 13, t))
    assert "corners" not in P.build(game(sport="nfl"), mm, None, "football", COR)
    assert "total" not in P.build(game(sport="nfl"), mm, None, "football")                      # fuera del fútbol, sin línea de mercado no hay total/hándicap

def test_corners_of_lee_wonCorners_del_boxscore():
    mk = lambda ha, v: dict(homeAway=ha, statistics=[dict(name="wonCorners", displayValue=str(v))])
    assert P.corners_of(dict(boxscore=dict(teams=[mk("home", 11), mk("away", 5)]))) == dict(home=11, away=5)
    assert P.corners_of(dict(boxscore=dict(teams=[dict(homeAway="home", statistics=[]), mk("away", 5)]))) is None
    assert P.corners_of({}) is None

def _summ(h, a, hid="1", aid="2"):
    mk = lambda ha, v: dict(homeAway=ha, statistics=[dict(name="wonCorners", displayValue=str(v))])
    return dict(boxscore=dict(teams=[mk("home", h), mk("away", a)]))

def test_corners_info_promedia_a_favor_y_en_contra(monkeypatch):
    import server.cache as C
    table = {str(i): (_summ(7, 3) if i < 100 else _summ(4, 6)) for i in list(range(1, 7)) + list(range(101, 107))}
    async def fake(url, ttl=0, params=None, **k): return table[params["event"]]
    monkeypatch.setattr(C, "get_json", fake)
    rowsH = dict(recent=[dict(id=str(i), home=True) for i in range(1, 7)])        # el local jugó de local: 7 a favor / 3 en contra
    rowsA = dict(recent=[dict(id=str(i), home=False) for i in range(101, 107)])    # la visita jugó de visita: 6 a favor / 4 en contra
    r = asyncio.run(P.corners_info("mex.1", "soccer/mex.1", rowsH, rowsA, "1", "2"))
    assert r["home"] == pytest.approx((7 + 4) / 2) and r["away"] == pytest.approx((6 + 3) / 2) and r["total"] == pytest.approx(10)
    assert r["n"] == [6, 6] and r["line"] % 1 == .5 and r["sd"] >= 2
    # menos de 4 partidos con dato -> None (no se inventa)
    table.update({str(i): {} for i in range(1, 6)})
    assert asyncio.run(P.corners_info("mex.1", "soccer/mex.1", rowsH, rowsA, "1", "2")) is None

def test_nba_nfl_marcador_coherente_y_tenis_home_first():
    mm = dict(mu=-6.0, sigma=13.0, exp_total=44.5, tsigma=10.0, p_home=.3, p_away=.7, total=lambda t: M.cover_normal(44.5, 10, t), cover=lambda t: M.cover_normal(-6, 13, t))
    p = P.build(game(sport="nfl"), mm, dict(total=dict(over=dict(line=43.5)), spread=dict(home=dict(line=6.5)), book="B"), "football")
    assert p["winner"]["side"] == "away" and p["score"]["away"] > p["score"]["home"] and p["total"]["line_src"] == "mercado"
    t = P.build(dict(best_of=3), M.tennis_model(9000, 6000), None, "tennis")
    assert t["winner"]["side"] == "home" and t["score"]["home"] == 2 and len(t["score"]["sets"]) >= 2 and t["total"]["line_src"] == "modelo"   # sin mercado: línea de juegos del modelo, marcada

def test_save_se_actualiza_antes_del_inicio_y_se_bloquea_despues(db):
    g = game()
    p1 = P.build(g, soc_model(1.9, .8), None, "soccer"); p2 = P.build(g, soc_model(.8, 1.9), None, "soccer")
    assert P.save(g, p1, now=NOW) and P.save(g, p2, now=NOW + 60)
    assert P.get("mex.1", "1")["pred"]["winner"]["side"] == "away"                           # se actualizó antes del inicio
    g2 = dict(g, state="in")
    assert not P.save(g2, p1, now=NOW + 7200)                                                 # ya empezó: no se escribe
    assert not P.save(dict(g, date=iso(NOW - 10)), p1, now=NOW)                               # fecha pasada: tampoco
    P.save(g, p1, now=NOW + 3599)
    assert P.get("mex.1", "1")["pred"]["winner"]["side"] == "home"
    with P.history._lock:                                                                      # tras calificar, una nueva escritura no la pisa
        c = P._c(); c.execute("UPDATE predictions SET status='GRADED'"); c.commit()
    P.save(g, p2, now=NOW + 3600)
    assert P.get("mex.1", "1")["pred"]["winner"]["side"] == "home"

def test_attach_pre_vivo_y_final(db):
    g = game(); out = dict(game=g, pred=P.build(g, soc_model(), None, "soccer", COR))
    o = P.attach(copy.deepcopy(out), now=NOW)
    assert o["pred"]["locked"] is False and o["pred"]["corners"]
    live = dict(game=dict(g, state="in"), pred=P.build(g, soc_model(.5, 2), None, "soccer"))
    o2 = P.attach(live, now=NOW + 4000)
    assert o2["pred"]["locked"] is True and o2["pred"]["winner"]["side"] == "home"           # la guardada, no la nueva

def _row(p, sport="futbol"): return dict(pred=p, sport=sport)

def test_grade_row_soccer_incluye_corners_y_hándicap_visita():
    p = P.build(game(), soc_model(), None, "soccer", COR)
    p["score"].update(home=3, away=1); p["winner"]["side"] = "home"; p["total"].update(side="over", line=2.5); p["spread"].update(side="home", line=-1.5); p["corners"].update(side="over", line=9.5)
    r = P.grade_row(_row(p), dict(state="final", home=3, away=1, corners_total=12), now=NOW)
    assert (r["r_ml"], r["r_total"], r["r_spread"], r["r_corners"], r["r_score"]) == ("GANADO",) * 5 and r["score_text"] == "3-1"
    r = P.grade_row(_row(p), dict(state="final", home=1, away=0, corners_total=8), now=NOW)
    assert (r["r_ml"], r["r_total"], r["r_spread"], r["r_corners"], r["r_score"]) == ("GANADO", "PERDIDO", "PERDIDO", "PERDIDO", "PERDIDO")
    r = P.grade_row(_row(p), dict(state="final", home=1, away=0), now=NOW)                    # sin dato de córners: queda sin calificar
    assert "r_corners" not in r
    # hándicap del visitante (+1.5 en línea del local = -1.5 visitante)
    p["winner"]["side"] = "away"; p["spread"].update(side="away", line=1.5)
    assert P.grade_row(_row(p), dict(state="final", home=0, away=2), now=NOW)["r_spread"] == "GANADO"
    assert P.grade_row(_row(p), dict(state="final", home=1, away=2), now=NOW)["r_spread"] == "PERDIDO"

def test_grade_row_tenis_y_void():
    t = P.build(dict(best_of=3), M.tennis_model(9000, 6000), None, "tennis")
    r = P.grade_row(_row(t, "tenis"), dict(state="final", home=2, away=0, sets=t["score"]["sets"], score_text="x"), now=NOW)
    assert r["r_ml"] == "GANADO" and r["r_sets"] == "GANADO" and r["r_score"] == "GANADO"
    assert P.grade_row(_row(t, "tenis"), dict(state="final", home=0, away=2, sets=[[3, 6], [3, 6]]), now=NOW)["r_ml"] == "PERDIDO"
    assert P.grade_row(_row(t, "tenis"), dict(state="void", note="WO"), now=NOW)["status"] == "ANULADO"
    assert P.grade_row(_row(t, "tenis"), dict(state="pending"), now=NOW) is None

def test_grade_pending_califica_y_stats_por_tipo(db, monkeypatch):
    import server.grading as G, server.cache as C
    g = game(); p = P.build(g, soc_model(), None, "soccer", COR)
    p["score"].update(home=3, away=1); p["winner"]["side"] = "home"; p["corners"].update(side="over", line=9.5); p["total"].update(side="over", line=2.5); p["spread"].update(side="home", line=-1.5)
    P.save(g, p, now=NOW)
    async def fake_res(r): return dict(state="final", home=3, away=1)
    async def fake_get(url, ttl=0, params=None, **k): return _summ(8, 5)
    monkeypatch.setattr(G, "fetch_result", fake_res); monkeypatch.setattr(C, "get_json", fake_get)
    assert asyncio.run(P.grade_pending(now=NOW + 99999))["graded"] == 1
    s = P.stats()
    assert s["graded"] == 1 and s["pending"] == 0
    for k in ("ml", "total", "spread", "corners", "score"): assert s[k]["hit"] == 1 and s[k]["pct"] == 100
    assert s["recent"][0]["corners"] == "GANADO" and s["recent"][0]["score_text"] == "3-1"
    assert P.attach(dict(game=dict(g, state="post")), now=NOW + 99999)["pred"]["result"]["corners"] == "GANADO"

def test_api_record_incluye_pred(db):
    from fastapi.testclient import TestClient
    from server import main
    r = TestClient(main.app).get("/api/record").json()
    assert "pred" in r and set(("ml", "total", "spread", "corners", "score", "graded", "pending")) <= set(r["pred"])


# ---------------------------------------------------------------- marcador exacto: variedad y coherencia con las líneas / picks del propio juego
def _consistent(p, fam):
    """Ganador, total y hándicap mostrados deben concordar con el marcador exacto (juegos totales en tenis)."""
    sc = p["score"]
    h, a = (sc["games"] if fam == "tennis" else (sc["home"], sc["away"]))
    w = p["winner"]["side"]
    assert (w == "draw" and sc["home"] == sc["away"]) or (w == "home" and sc["home"] > sc["away"]) or (w == "away" and sc["away"] > sc["home"]), (w, sc)
    t = p.get("total")
    if t and h + a != t["line"]: assert (h + a > t["line"]) == (t["side"] == "over"), (t, sc)
    s = p.get("spread")
    if s and h - a + s["line"] != 0: assert (h - a + s["line"] > 0) == (s["side"] == "home"), (s, sc)

def test_futbol_over_35_no_puede_dar_2_1_ni_under_25_dar_3_goles():
    od = lambda T: dict(total=dict(over=dict(line=T)), book="X")
    p = P.build(game(), soc_model(2.0, 1.2), od(3.5), "soccer", picks=dict(lean=dict(market="Total", side="over", line=3.5, status="PICK"), status="PICK", candidates=[]))
    assert p["score"]["home"] + p["score"]["away"] >= 4 and p["total"]["side"] == "over" and p["total"]["aligned"] == "pick"
    _consistent(p, "soccer")
    p = P.build(game(), soc_model(1.5, 1.2), od(2.5), "soccer", picks=dict(lean=dict(market="Total", side="under", line=2.5, status="LEAN"), status="LEAN", candidates=[]))
    assert p["score"]["home"] + p["score"]["away"] <= 2 and p["total"]["side"] == "under"
    _consistent(p, "soccer")

def test_futbol_pick_de_ganador_y_handicap_se_respetan():
    pk = lambda **kw: dict(lean=dict(status="PICK", **kw), status="PICK", candidates=[])
    p = P.build(game(), soc_model(1.7, 1.3), None, "soccer", picks=pk(market="ML", side="away"))
    assert p["winner"]["side"] == "away" and p["score"]["away"] > p["score"]["home"]
    p = P.build(game(), soc_model(1.7, 1.3), dict(spread=dict(home=dict(line=-1.5)), book="X"), "soccer", picks=pk(market="Spread", side="home", line=-1.5))
    assert p["score"]["home"] - p["score"]["away"] >= 2 and p["spread"]["side"] == "home"
    _consistent(p, "soccer")

def test_futbol_picks_contradictorios_se_corrigen_y_nunca_se_muestra_una_salida_inconsistente():
    # modelo: gana visitante, pero el pick es hándicap local +0.5 (=local gana o empata): se respeta el pick y el ganador se corrige al marcador
    p = P.build(game(), soc_model(.9, 1.7), None, "soccer", picks=dict(lean=dict(market="Spread", side="home", line=.5, status="PICK"), status="PICK", candidates=[]))
    _consistent(p, "soccer")
    assert p["score"]["home"] >= p["score"]["away"] and p["winner"]["side"] in ("home", "draw") and "winner" in (p.get("adjusted") or [])
    # sin ningún marcador posible (Under 0.5 con ganador local) se descarta la línea débil
    p = P.build(game(), soc_model(2.4, .5), dict(total=dict(over=dict(line=.5)), book="X"), "soccer", picks=dict(lean=dict(market="Total", side="under", line=.5, status="PICK"), status="PICK", candidates=[]))
    _consistent(p, "soccer"); assert p["score"]["home"] + p["score"]["away"] == 0

def test_futbol_barrido_de_lambdas_siempre_coherente_y_con_variedad():
    seen = set()
    for lh in (0.6, 0.9, 1.2, 1.6, 2.0, 2.6):
        for la in (0.5, 0.9, 1.3, 1.8, 2.4):
            for T in (None, 1.5, 2.5, 3.5):
                for sp in (None, -1.5, -0.5, 0.5):
                    od = dict(book="X"); 
                    if T: od["total"] = dict(over=dict(line=T))
                    if sp is not None: od["spread"] = dict(home=dict(line=sp))
                    p = P.build(game(), soc_model(lh, la), od, "soccer")
                    _consistent(p, "soccer"); seen.add((p["score"]["home"], p["score"]["away"]))
    assert {(1, 0), (0, 1), (2, 0), (2, 1)} <= seen and len(seen) >= 8

def test_margen_nba_respeta_total_y_handicap_del_pick():
    mm = dict(mu=3.0, sigma=12.0, exp_total=222.0, tsigma=18.0, p_home=.6, p_away=.4, total=lambda t: M.cover_normal(222, 18, t), cover=lambda t: M.cover_normal(3, 12, t))
    od = dict(total=dict(over=dict(line=228.5)), spread=dict(home=dict(line=-3.5)), book="B")
    p = P.build(game(sport="nba"), mm, od, "basketball", picks=dict(lean=dict(market="Total", side="over", line=228.5, status="PICK"), status="PICK", candidates=[]))
    assert p["score"]["home"] + p["score"]["away"] > 228.5; _consistent(p, "margin")

def test_tenis_barrido_coherente_variedad_y_mejor_de_5():
    seen, sets_seen = set(), set()
    for pa, pb in ((9000, 8000), (9000, 4000), (9000, 1500), (3000, 6000), (1500, 9000), (5200, 5000)):
        for bo in (3, 5):
            for T in (None, 16.5, 20.5, 22.5, 24.5, 38.5):
                od = dict(book="X"); 
                if T: od["total"] = dict(over=dict(line=T if bo == 3 else T + 14))
                p = P.build(dict(best_of=bo), M.tennis_model(pa, pb), od, "tennis")
                _consistent(p, "tennis")
                sc = p["score"]
                assert sum(1 for x in sc["sets"] if x[0] > x[1]) == sc["home"] and sum(1 for x in sc["sets"] if x[1] > x[0]) == sc["away"]   # juegos por set suman al marcador de sets
                assert max(sc["home"], sc["away"]) == (2 if bo == 3 else 3) and all(max(x) in (6, 7) for x in sc["sets"])
                seen.add((sc["home"], sc["away"], bo)); sets_seen.update(tuple(x) for x in sc["sets"])
    assert len({s for s in seen if s[2] == 3}) >= 3 and len({s for s in seen if s[2] == 5}) >= 3        # 2-0 / 2-1 y 3-0 / 3-1 / 3-2 según el partido
    assert len(sets_seen) >= 6                                                                          # no siempre 6-4 6-4

def test_tenis_over_obliga_a_mas_juegos_y_under_a_menos():
    mk = lambda T: dict(total=dict(over=dict(line=T)), book="X")
    pk = lambda side, T: dict(lean=dict(market="Total", side=side, line=T, status="PICK"), status="PICK", candidates=[])
    o = P.build(dict(best_of=3), M.tennis_model(9000, 5000), mk(22.5), "tennis", picks=pk("over", 22.5))
    u = P.build(dict(best_of=3), M.tennis_model(9000, 5000), mk(22.5), "tennis", picks=pk("under", 22.5))
    assert sum(o["score"]["games"]) > 22.5 > sum(u["score"]["games"]) and o["total"]["side"] == "over" and u["total"]["side"] == "under"
