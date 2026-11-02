"""Fútbol: el primer equipo es el LOCAL en todo (tarjetas, detalle, mercados 1-X-2, marcadores); el resto de deportes sigue 'visitante @ local'."""
import json, os, re, shutil, subprocess
import pytest
from server import grading as G, record as R, history

ROOT = os.path.join(os.path.dirname(__file__), "..")

def test_grading_text_futbol_local_primero():
    row = dict(sport="futbol", market="ml", selection="home", line=None, odds=-110, start_ts=0, home="América", away="Pumas")
    r = G.grade_row(row, dict(state="final", home=2, away=1))
    assert r[2] == "América 2 - 1 Pumas" and r[3] == 2 and r[4] == 1
    row = dict(row, sport="nba", home="Utah", away="Portland")
    assert G.grade_row(row, dict(state="final", home=100, away=90))[2] == "Portland 90 @ Utah 100"      # EE. UU.: sin cambios

def test_migra_marcador_guardado_de_futbol(db):
    with history._lock:
        c = R._c()
        c.execute("INSERT INTO picks(sport,league,eid,start_ts,home,away,market,selection,status,score_text,final_home,final_away) VALUES "
                  "('futbol','mex.1','1',1,'América','Pumas','ml','home','GANADO','Pumas 1 @ América 2',2,1),"
                  "('nba','nba','2',1,'Utah','Portland','ml','home','GANADO','Portland 90 @ Utah 100',100,90)")
        c.commit(); R.reset_for_tests(); c = R._c()
        rows = {r[0]: r[1] for r in c.execute("SELECT sport, score_text FROM picks")}
    assert rows["futbol"] == "América 2 - 1 Pumas" and rows["nba"] == "Portland 90 @ Utah 100"

@pytest.mark.skipif(not shutil.which("node"), reason="sin node")
def test_orden_de_equipos_en_frontend():
    src = open(os.path.join(ROOT, "static", "app.js"), encoding="utf-8").read()
    pick = "\n".join(re.search(rf"^const {n} = .*$", src, re.M).group(0) for n in ("isSoc", "homeFirst", "sides", "vsMark"))
    js = pick + "\nconsole.log(JSON.stringify([sides({sport:'futbol'}), sides({sport:'nba'}), sides({sport:'tenis'}), vsMark({sport:'futbol'}), vsMark({sport:'nfl'})]))"
    out = json.loads(subprocess.check_output(["node", "-e", js], text=True))
    assert out == [["home", "away"], ["away", "home"], ["home", "away"], "vs", "@"]      # tenis también va local primero (como fútbol)
    # el render de tarjetas y héroe usa el orden por deporte (no away/home fijos)
    assert "sides(g).map(sd=>team(g[sd],sd))" in src and "heroSide(g,d,sides(g)[0])" in src
