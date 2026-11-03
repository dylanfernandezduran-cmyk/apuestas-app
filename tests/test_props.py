"""Props de jugadores (pt84u): parseo de propBets (DraftKings vía ESPN), bitácora, tendencias, modo referencia y «Sin línea». Sin red: fuentes simuladas."""
import asyncio, re
from pathlib import Path
import pytest
from server import props as P

ROOT = Path(__file__).resolve().parent.parent

def item(aid, tname, price, tgt, open_=None, over=None, under=None):
    it = {"athlete": {"$ref": f"http://x/v2/sports/basketball/leagues/nba/seasons/2027/athletes/{aid}?lang=en"}, "type": {"id": "1", "name": tname},
          "odds": {"american": {"value": str(price)}}, "lastUpdated": "2026-11-03T06:01Z"}
    if tgt is not None:
        it["current"] = {"target": {"value": tgt}}; it["open"] = {"target": {"value": open_ if open_ is not None else tgt}}
    else: it["current"] = {}
    if over is not None: it["current"]["over"] = {"american": over}
    if under is not None: it["current"]["under"] = {"american": under}
    return it

def test_parse_over_under_por_orden_del_par():
    ix = P.parse_items([item("1", "Total Points", "-103", 26.5), item("1", "Total Points", "-123", 26.5)], "basketball")
    p = ix[("1", "pts")]
    assert p["line"] == 26.5 and p["over"] == -103 and p["under"] == -123 and p["kind"] == "ou"           # el 1º del par es el Más

def test_parse_formato_con_over_under_explicitos_y_solo_un_precio():
    ix = P.parse_items([item("2", "Total Rebounds", "+110", 7.5, over="+110", under="-140")], "basketball")
    assert ix[("2", "reb")]["over"] == 110 and ix[("2", "reb")]["under"] == -140
    solo = P.parse_items([item("3", "Total Assists", "-120", 5.5)], "basketball")[("3", "ast")]
    assert solo["over"] is None and solo["under"] is None                                              # un solo precio sin par: no se adivina el lado

def test_milestones_son_mas_de_n_menos_medio_y_ou_gana():
    ms = P.parse_items([item("4", "Points Milestones", "+150", 20)], "basketball")[("4", "pts")]
    assert ms["line"] == 19.5 and ms["kind"] == "ms" and ms["over"] == 150 and ms["under"] is None
    both = P.parse_items([item("4", "Points Milestones", "+150", 20), item("4", "Total Points", "-110", 24.5), item("4", "Total Points", "-110", 24.5)], "basketball")
    assert both[("4", "pts")]["kind"] == "ou" and both[("4", "pts")]["line"] == 24.5

def test_mercados_anytime_tienen_linea_fija_y_sin_linea_no_se_incluye():
    ix = P.parse_items([item("5", "Anytime Goalscorer", "+155", None)], "hockey")
    assert ix[("5", "goals")]["line"] == .5 and ix[("5", "goals")]["kind"] == "yes"
    assert P.parse_items([item("6", "Total Points", "-110", None)], "basketball") == {}                  # sin línea numérica: se ignora, no se inventa
    assert P.parse_items([item("7", "Tipo Desconocido", "-110", 5.5)], "basketball") == {}
    assert P.parse_items([item("8", "1st Quarter Total Points", "-110", 5.5)], "basketball") == {}      # sólo el partido completo

def test_goles_hockey_no_pisa_el_anytime_con_la_escalera():
    ix = P.parse_items([item("9", "Anytime Goalscorer", "+155", None), item("9", "Goals Milestones", "+1600", 2)], "hockey")
    assert ix[("9", "goals")]["line"] == .5

GL = {"names": ["points", "totalRebounds", "assists", "threePointFieldGoalsMade-threePointFieldGoalsAttempted"],
      "events": {"1": {"gameDate": "2026-10-30T00:00Z", "opponent": {"abbreviation": "LAL"}, "atVs": "vs", "gameResult": "W", "score": "110-100"},
                 "2": {"gameDate": "2026-10-28T00:00Z", "opponent": {"abbreviation": "MIN"}, "atVs": "@", "gameResult": "L", "score": "90-95"},
                 "3": {"gameDate": "2026-10-01T00:00Z", "opponent": {"abbreviation": "XXX"}, "atVs": "@", "gameResult": "W", "score": "1-0"}},
      "seasonTypes": [{"displayName": "2026-27 Regular Season", "categories": [{"events": [{"eventId": "2", "stats": ["24", "5", "6", "3-9"]}, {"eventId": "1", "stats": ["31", "4", "7", "5-11"]}]}]},
                      {"displayName": "2026 Preseason", "categories": [{"events": [{"eventId": "3", "stats": ["99", "9", "9", "9-9"]}]}]}]}

def test_gamelog_orden_reciente_primero_y_sin_pretemporada():
    g = P.parse_gamelog(GL)
    assert [x["eid"] for x in g] == ["1", "2"] and g[0]["opp"] == "LAL" and g[0]["home"] and not g[1]["home"]
    assert P.stat_value("basketball", "pts", g[0]["s"]) == 31 and P.stat_value("basketball", "pra", g[0]["s"]) == 42
    assert P.stat_value("basketball", "fg3", g[0]["s"]) == 5                                              # «5-11» -> hechos
    assert P.parse_gamelog(None) == []

def test_stat_value_none_si_falta_una_columna_y_beisbol_derivadas():
    assert P.stat_value("basketball", "pra", {"points": "10", "assists": "2"}) is None                  # falta rebotes: no se suma parcial
    s = {"hits": "3", "doubles": "1", "triples": "0", "homeRuns": "1"}
    assert P.stat_value("baseball", "tb", s) == 3 + 1 + 0 + 3 and P.stat_value("baseball", "singles", s) == 1
    assert P.stat_value("baseball", "tb", {"hits": "3"}) is None
    assert P.stat_value("basketball", "inexistente", {}) is None

def test_hit_stats_over_under_y_push():
    v = [30, 20, 25, 25, None, 10]
    o = P.hit_stats(v, 25, "over", 10); u = P.hit_stats(v, 25, "under", 10)
    assert (o["hit"], o["n"], o["push"]) == (1, 5, 2) and (u["hit"], u["n"]) == (2, 5)
    assert o["pct"] == pytest.approx(1 / 3)
    assert P.hit_stats([], 5)["pct"] is None

def test_linea_de_referencia_es_x5_y_exige_3_juegos():
    r = P.reference_line([20, 24, 26, 30, 22])
    assert r["line"] == 24.5 and r["n"] == 5 and r["avg"] == pytest.approx(24.4)
    assert P.reference_line([20, 24]) is None and P.reference_line([None, None, None, 5]) is None

def _patch(monkeypatch, idx, log=GL):
    async def ev(league, eid, ttl=300): return idx.get(eid, {})
    async def info(league, aid): return {"id": aid, "name": "Jugador " + aid, "jersey": "7", "pos": "G", "pos_name": "Guard", "img": None, "team": {"id": "9", "abbr": "GS", "name": "GS", "logo": None}}
    async def gl(league, aid, need=20): return P.parse_gamelog(log)
    monkeypatch.setattr(P, "event_props", ev); monkeypatch.setattr(P, "athlete_info", info); monkeypatch.setattr(P, "gamelog", gl)

def test_player_prop_linea_real_e_historica_por_juego(monkeypatch):
    mk = lambda line, o, u: {("5", "pts"): dict(aid="5", key="pts", kind="ou", line=line, open=line, over=o, under=u, updated=None, type="Total Points")}
    _patch(monkeypatch, {"E": mk(26.5, -103, -123), "1": mk(24.5, -110, -110)})        # el juego «2» no tiene línea histórica
    r = asyncio.run(P.player_prop("nba", "E", "5", "pts"))
    assert r["line"]["value"] == 26.5 and r["line"]["ref"] is False and r["line"]["over"] == -103 and r["line"]["src"].startswith("DraftKings")
    g = {x["eid"]: x for x in r["games"]}
    assert g["1"]["value"] == 31 and g["1"]["line_hist"] == 24.5 and "line_hist" not in g["2"] and r["hist_n"] == 10        # nunca se rellena una línea que no existe

def test_player_prop_sin_linea_usa_referencia_rotulada(monkeypatch):
    big = {"names": ["points"], "events": {str(i): {"gameDate": f"2026-10-{i+1:02d}T00:00Z", "opponent": {"abbreviation": "AAA"}, "atVs": "vs"} for i in range(5)},
           "seasonTypes": [{"displayName": "Regular Season", "categories": [{"events": [{"eventId": str(i), "stats": [str(20 + i)]} for i in range(5)]}]}]}
    _patch(monkeypatch, {}, big)
    r = asyncio.run(P.player_prop("nba", "E", "5", "pts"))
    assert r["line"]["ref"] is True and r["line"]["src"] is None and r["line"]["over"] is None and r["line"]["value"] == 22.5 and r["line"]["ref_n"] == 5
    assert all("line_hist" not in g for g in r["games"])

def test_player_prop_sin_linea_ni_historial_suficiente_dice_sin_linea(monkeypatch):
    _patch(monkeypatch, {})                                                                          # sólo 2 juegos reales en la bitácora
    r = asyncio.run(P.player_prop("nba", "E", "5", "pts"))
    assert r["line"]["value"] is None and r["line"]["ref"] is True and len(r["games"]) == 2

def test_tenis_no_inventa_props():
    r = asyncio.run(P.game_props("atp", "1"))
    assert r["mode"] == "none" and r["players"] == [] and "Tenis" in r["note"]

def test_clave_invalida_devuelve_none(monkeypatch):
    _patch(monkeypatch, {})
    assert asyncio.run(P.player_prop("nba", "E", "5", "nada")) is None

def test_endpoints_y_validaciones(monkeypatch):
    from fastapi.testclient import TestClient
    from server import main
    c = TestClient(main.app)
    assert c.get("/api/props/zzz/1").status_code == 404
    assert c.get("/api/prop/nba/1/abc/pts").status_code == 400
    async def none(*a, **k): return None
    monkeypatch.setattr(main.PROPS, "player_prop", none)
    assert c.get("/api/prop/nba/1/123/pts").status_code == 404

def test_frontend_cableado_y_estilos_sin_choques():
    js = (ROOT / "static" / "props.js").read_text(); dj = (ROOT / "static" / "detalle.js").read_text(); app = (ROOT / "static" / "app.js").read_text()
    css = (ROOT / "static" / "style.css").read_text().split("Props de jugadores (pt84u)")[-1]
    assert "function dProps" in js and "function viewProp" in js and "dProps(d)" in dj and "viewProp(" in app and "propsInit()" in app
    assert "'prop'" in app and "d.kind==='tennis'" in js                                                   # ruta propia; tenis sin sección
    assert all(sel.startswith("#app.gd .pp-") for sel in re.findall(r"^(#app\.gd [^{,]+)\{", css, re.M))   # todo el CSS de props va acotado y con prefijo único
    for needle in ("Sin línea", "REFERENCIA", "Cumplió", "Falló", "/api/props/", "/api/prop/"): assert needle in js
